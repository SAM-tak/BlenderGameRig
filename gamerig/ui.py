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
import re

from .utils import (
    get_rig_type, MetarigError, write_metarig, write_widget, unique_name, get_keyed_frames,
    bones_in_frame, overwrite_prop_animation, get_rig_name, copy_attributes
)
from . import rig_lists, generate


class ArmaturePanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_main"
    bl_label = "GameRig"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and (context.object.data.gamerig.rig_ui_template or 'gamerig_rig_ui_template' in context.object.data)

    def draw(self, context):
        if 'gamerig_rig_ui_template' in context.object.data:
            self.layout.label(text='This metarig armature has old format data.', icon='ERROR')
            self.layout.operator(MigrateOperator.bl_idname)
            return
        
        layout = self.layout
        obj = context.object
        gparam = context.window_manager.gamerig
        armature = obj.data

        ## Layers
        # Ensure that the layers exist
        # Can't add while drawing, just use button
        if len(armature.gamerig.layers) < 30:
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

                for i, layer in enumerate(armature.gamerig.layers):
                    # note: layer == armature.gamerig.layers[i]
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
                    row.prop(layer, "name", text="")
                    row.prop(layer, "row", text="UI Row")
                    icon = 'RADIOBUT_ON' if layer.selset else 'RADIOBUT_OFF'
                    row.prop(layer, "selset", text="", toggle=True, icon=icon)
                    row.prop(layer, "group", text="Bone Group")
                    if layer.group == 0:
                        row.label(text='None')
                    else:
                        row.label(text=armature.gamerig.colors[layer.group-1].name)

                # buttons
                col = col2.column()
                col.label(text="Reserved:")
                reserved_names = {30: 'MCH', 31: 'Original'}
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
            color_sets = obj.data.gamerig.colors
            idx = obj.data.gamerig.colors_index

            row = box.row()
            row.operator(UseStandardColorsOperator.bl_idname, icon='FILE_REFRESH', text='')
            row = row.row(align=True)
            row.prop(armature.gamerig.selection_colors, 'select', text='')
            row.prop(armature.gamerig.selection_colors, 'active', text='')
            row = box.row(align=True)
            icon = 'LOCKED' if armature.gamerig.colors_lock else 'UNLOCKED'
            row.prop(armature.gamerig, 'colors_lock', text = 'Unified select/active colors', icon=icon)
            row.operator(ApplySelectionColorsOperator.bl_idname, icon='FILE_REFRESH', text='Apply')
            row = box.row()
            row.template_list(BoneGroupsUIList.bl_idname, "", armature.gamerig, "colors", armature.gamerig, "colors_index")

            col = row.column(align=True)
            col.operator(AddBoneGroupOperator.bl_idname, icon='ZOOM_IN', text="")
            col.operator(RemoveBoneGroupOperator.bl_idname, icon='ZOOM_OUT', text="").idx = obj.data.gamerig.colors_index
            col.menu(BoneGroupsSpecialsMenu.bl_idname, icon='DOWNARROW_HLT', text="")
            row = box.row()
            row.prop(armature.gamerig, 'theme_to_add', text = 'Theme')
            op = row.operator(AddBoneGroupThemeOperator.bl_idname, text="Add From Theme")
            op.theme = armature.gamerig.theme_to_add
            row = box.row()
            row.operator(AddBoneGroupsOperator.bl_idname, text="Add Standard")

        ## Generation
        if obj.mode in {'POSE', 'OBJECT'}:
            layout.row().prop(armature.gamerig, "rig_name", text="Rig Name")
            rig_name = get_rig_name(obj)
            target = next((i for i in context.collection.objects if i != obj and i.type == 'ARMATURE' and i.name == rig_name), None)
            if target:
                layout.row().box().label(text="Overwrite to '%s'" % target.name, icon='INFO')
                layout.row().operator(GenerateOperator.bl_idname, text="Regenerate Rig", icon='POSE_HLT')
                if obj.mode == 'OBJECT':
                    layout.separator()
                    row = layout.row(align=True).split(factor=0.06)
                    row.label()
                    row = row.split()
                    row.operator(ToggleArmatureReferenceOperator.bl_idname, text="Toggle armature metarig/generated", icon='ARROW_LEFTRIGHT')
            else:
                rig_name = unique_name(bpy.data.objects.keys(), rig_name)
                layout.row().box().label(text="Create new armature '%s'" % rig_name, icon='INFO')
                layout.row().operator(GenerateOperator.bl_idname, text="Generate New Rig", icon='POSE_HLT')

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
            layout.row().template_list("UI_UL_list", "gamerig_type", gparam, "types", gparam, 'active_type')

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

        groups = ['Root', 'IK', 'Special', 'Tweak', 'FK', 'Extra']

        for g in groups:
            if g in armature.gamerig.colors.keys():
                continue

            armature.gamerig.colors.add()
            armature.gamerig.colors[-1].name = g

            armature.gamerig.colors[g].select = Color((0.3140000104904175, 0.7839999794960022, 1.0))
            armature.gamerig.colors[g].active = Color((0.5490000247955322, 1.0, 1.0))
            armature.gamerig.colors[g].standard_colors_lock = True

            if g == "Root":
                armature.gamerig.colors[g].normal = Color((0.43529415130615234, 0.18431372940540314, 0.41568630933761597))
            if g == "IK":
                armature.gamerig.colors[g].normal = Color((0.6039215922355652, 0.0, 0.0))
            if g== "Special":
                armature.gamerig.colors[g].normal = Color((0.9568628072738647, 0.7882353663444519, 0.0470588281750679))
            if g== "Tweak":
                armature.gamerig.colors[g].normal = Color((0.03921568766236305, 0.21176472306251526, 0.5803921818733215))
            if g== "FK":
                armature.gamerig.colors[g].normal = Color((0.11764706671237946, 0.5686274766921997, 0.03529411926865578))
            if g== "Extra":
                armature.gamerig.colors[g].normal = Color((0.9686275124549866, 0.250980406999588, 0.0941176563501358))

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

        current_theme = bpy.context.preferences.themes.items()[0][0]
        theme = bpy.context.preferences.themes[current_theme]

        armature.gamerig.selection_colors.select = theme.view_3d.bone_pose
        armature.gamerig.selection_colors.active = theme.view_3d.bone_pose_active

        # for col in armature.gamerig.colors:
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

        #current_theme = bpy.context.preferences.themes.items()[0][0]
        #theme = bpy.context.preferences.themes[current_theme]

        for col in armature.gamerig.colors:
            col.select = armature.gamerig.selection_colors.select
            col.active = armature.gamerig.selection_colors.active

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

        armature.gamerig.colors.add()
        armature.gamerig.colors[-1].name = unique_name(armature.gamerig.colors, 'Group')

        current_theme = bpy.context.preferences.themes.items()[0][0]
        theme = bpy.context.preferences.themes[current_theme]

        armature.gamerig.colors[-1].normal = theme.view_3d.wire
        armature.gamerig.colors[-1].normal.hsv = theme.view_3d.wire.hsv
        armature.gamerig.colors[-1].select = theme.view_3d.bone_pose
        armature.gamerig.colors[-1].select.hsv = theme.view_3d.bone_pose.hsv
        armature.gamerig.colors[-1].active = theme.view_3d.bone_pose_active
        armature.gamerig.colors[-1].active.hsv = theme.view_3d.bone_pose_active.hsv

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

        if self.theme in armature.gamerig.colors.keys():
            return {'FINISHED'}
        armature.gamerig.colors.add()
        armature.gamerig.colors[-1].name = self.theme

        id = int(self.theme[-2:]) - 1

        theme_color_set = bpy.context.preferences.themes[0].bone_color_sets[id]

        armature.gamerig.colors[-1].normal = theme_color_set.normal
        armature.gamerig.colors[-1].select = theme_color_set.select
        armature.gamerig.colors[-1].active = theme_color_set.active

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
        obj.data.gamerig.colors.remove(self.idx)

        # set layers references to 0
        for l in obj.data.gamerig.layers:
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

        for i, col in enumerate(obj.data.gamerig.colors):
            obj.data.gamerig.colors.remove(0)
            # set layers references to 0
            for l in obj.data.gamerig.layers:
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
        row2.enabled = not bpy.context.object.data.gamerig.colors_lock


class BoneGroupsSpecialsMenu(bpy.types.Menu):
    bl_idname = "GAMERIG_MT_bone_groups_specials"
    bl_label = 'GameRig Bone Groups Specials'

    def draw(self, context):
        layout = self.layout

        layout.operator(RemoveAllBoneGroupOperator.bl_idname)


class BonePanel(bpy.types.Panel):
    bl_idname      = "GAMERIG_PT_rig_type"
    bl_label       = "GameRig Rig Type"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = "bone"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.active_pose_bone and context.object.data.gamerig.rig_ui_template

    def draw(self, context):
        gparam = context.window_manager.gamerig
        bone = context.active_pose_bone
        category_name = str(gparam.category).replace(" ", "")
        rig_name = str(context.active_pose_bone.gamerig.name).replace(" ", "")

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
        row.prop_search(bone.gamerig, "name", gparam, "types", text="Rig type:")

        # Rig type parameters / Rig type non-exist alert
        if rig_name != "":
            try:
                rig = get_rig_type(rig_name)
                rig.Rig
            except (ImportError, AttributeError):
                row = layout.row()
                box = row.box()
                box.label(text="Rig \"%s\" does not exist!" % rig_name, icon='ERROR')
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
                    rig.parameters_ui(box, bone.gamerig)


class DevToolsPanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_dev_tools"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label       = "GameRig Dev Tools"

    @classmethod
    def poll(cls, context):
        return context.mode in ('EDIT_ARMATURE', 'EDIT_MESH') and context.preferences.addons['gamerig'].preferences.shows_dev_tools

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
          and 'gamerig_id' in context.active_object.data and context.preferences.addons['gamerig'].preferences.shows_dev_tools

    def draw(self, context):
        layout = self.layout
        layout.operator(RevealUnlinkedWidgetOperator.bl_idname)


def report_exception(operator, exception):
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

    operator.report({'ERROR'}, '\n'.join(message))


class InitLayerOperator(bpy.types.Operator):
    """Initialize armature gamerig layers"""

    bl_idname = "gamerig.init_layer"
    bl_label = "Add Layer Settings"
    bl_description = "Add GameRig Layers setting by default values"
    bl_options = {'UNDO'}

    def execute(self, context):
        obj = context.object
        arm = obj.data
        for i in range(1 + len(arm.gamerig.layers), 31):
            arm.gamerig.layers.add()
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


class GenerateProgressOperator(bpy.types.Operator):
    bl_idname = "gamerig.show_generation_progress"
    bl_label = 'Rig Generation Progress'
    bl_options = {'REGISTER'}  

    def modal(self, context, event):
        wm = context.window_manager
        print(self.ticks, wm.gamerig.progress_indicator)
        if event.type == 'TIMER':
            self.ticks += 1
        if self.ticks > 9:
            wm.gamerig.progress_indicator = 101 # done
            wm.event_timer_remove(self.timer)
            print('done')
            return {'CANCELLED'}
  
        wm.gamerig.progress_indicator = self.ticks*10
  
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        self.ticks = 0
        wm = context.window_manager
        wm.gamerig.progress_indicator = 0
        self.timer = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    # a variable where we can store the original draw funtion  
    prev_draw_f = lambda s,c: None
    
    @classmethod
    def register(cls):
        # save the original draw method of the Info header
        cls.prev_draw_f = bpy.types.STATUSBAR_HT_header.draw

        # create a new draw function
        def draw(self, context):
            # first call the original stuff
            cls.prev_draw_f(self, context)
            # then add the prop that acts as a progress indicator
            wm = context.window_manager
            progress = wm.gamerig.progress_indicator
            if progress >= 0 and progress <= 100:
                self.layout.separator()
                self.layout.prop(wm.gamerig, "progress_indicator", slider=True)

        # replace it
        bpy.types.STATUSBAR_HT_header.draw = draw

    @classmethod
    def unregister(cls):
        # recover the saved original draw method to the status bar
        bpy.types.STATUSBAR_HT_header.draw = cls.prev_draw_f


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
            report_exception(self, rig_exception)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        
        return { 'FINISHED' }


class ToggleArmatureReferenceOperator(bpy.types.Operator):
    """Toggle armature reference between metarig and generated rig."""

    bl_idname  = "gamerig.toggle_armature"
    bl_label   = "Toggle Rig"
    bl_description = "Toggle armature reference between metarig and generated rig"
    bl_options = {'UNDO'}

    def execute(self, context):
        metarig = context.object
        if metarig.data.gamerig.rig_ui_template:
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


class RenameBatchOperator(bpy.types.Operator):
    bl_idname = "gamerig.rename_batch"
    bl_label = "Rename Bones"
    bl_description = "Rename bones by regular expression"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode in ('EDIT_ARMATURE', 'EDIT_MESH') \
            or (context.mode == 'POSE' and context.object and context.object.animation_data and context.object.animation_data.action) \
            and context.window_manager.gamerig.rename_batch_find
    
    def execute(self, context):
        param = context.window_manager.gamerig
        if context.mode == 'EDIT_ARMATURE':
            if param.rename_batch_re:
                exp = re.compile(param.rename_batch_find)
                for i in context.object.data.edit_bones:
                    i.name = exp.sub(param.rename_batch_replace, i.name)
            else:
                for i in context.object.data.edit_bones:
                    i.name = i.name.replace(param.rename_batch_find, param.rename_batch_replace)
        elif context.mode == 'EDIT_MESH':
            if param.rename_batch_re:
                exp = re.compile(param.rename_batch_find)
                for i in context.object.vertex_groups:
                    i.name = exp.sub(param.rename_batch_replace, i.name)
            else:
                for i in context.object.vertex_groups:
                    i.name = i.name.replace(param.rename_batch_find, param.rename_batch_replace)
        else:
            datapathexp = re.compile(r'^(pose\.bones\[")(.+)("\].*)')
            if param.rename_batch_re:
                exp = re.compile(param.rename_batch_find)
                for i in context.object.animation_data.action.groups:
                    i.name = exp.sub(param.rename_batch_replace, i.name)
                for i in context.object.animation_data.action.fcurves:
                    match = datapathexp.match(i.data_path)
                    if match:
                        i.data_path = match.group(1) + exp.sub(param.rename_batch_replace, match.group(2)) + match.group(3)
            else:
                for i in context.object.animation_data.action.groups:
                    i.name = i.name.replace(param.rename_batch_find, param.rename_batch_replace)
                for i in context.object.animation_data.action.fcurves:
                    match = datapathexp.match(i.data_path)
                    if match:
                        i.data_path = match.group(1) + match.group(2).replace(param.rename_batch_find, param.rename_batch_replace) + match.group(3)

        return {'FINISHED'}


class RenameBatchPanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_RenameBatch"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label       = "Rename Batch"

    @classmethod
    def poll(cls, context):
        return context.mode in ('EDIT_ARMATURE', 'EDIT_MESH') \
            or (context.mode == 'POSE' and context.object and context.object.animation_data and context.object.animation_data.action)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        texts = {
            'EDIT_ARMATURE': 'Rename bones',
            'EDIT_MESH': 'Rename Vertex Groups',
            'POSE': 'Rename Animation Channels',
        }
        col.label(text=texts[context.mode])

        col.prop(context.window_manager.gamerig, 'rename_batch_find')
        col.prop(context.window_manager.gamerig, 'rename_batch_replace')
        col.prop(context.window_manager.gamerig, 'rename_batch_re')
        op = col.operator(RenameBatchOperator.bl_idname, text="Replace")


class MigrateOperator(bpy.types.Operator):
    bl_idname = "gamerig.migrate_armature"
    bl_label = "Migrate"
    bl_description = "Migrate old armature properties to new"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode in ('OBJECT', 'POSE')
    
    def execute(self, context):
        armature = context.object.data
        if 'gamerig_rig_ui_template' in armature:
            armature.gamerig.rig_ui_template = armature['gamerig_rig_ui_template']
            del armature['gamerig_rig_ui_template']
        
        if 'gamerig_rig_name' in armature:
            armature.gamerig.rig_name = armature['gamerig_rig_name']
            del armature['gamerig_rig_name']
        
        if 'gamerig_layers' in armature:
            armature.gamerig.layers.clear()
            for i in armature['gamerig_layers']:
                item = armature.gamerig.layers.add()
                for k, v in i.items():
                    item[k] = v
            del armature['gamerig_layers']
        
        if 'gamerig_colors' in armature:
            armature.gamerig.colors.clear()
            for i in armature['gamerig_colors']:
                item = armature.gamerig.colors.add()
                for k, v in i.items():
                    item[k] = v
            del armature['gamerig_colors']
        
        if 'gamerig_selection_colors' in armature:
            if 'select' in armature['gamerig_selection_colors']:
                armature.gamerig.selection_colors.select = armature['gamerig_selection_colors']['select']
            if 'active' in armature['gamerig_selection_colors']:
                armature.gamerig.selection_colors.active = armature['gamerig_selection_colors']['active']
            del armature['gamerig_selection_colors']
        
        if 'gamerig_colors_index' in armature:
            armature.gamerig.colors_index = armature['gamerig_colors_index']
            del armature['gamerig_colors_index']
        
        if 'gamerig_colors_lock' in armature:
            armature.gamerig.colors_lock = armature['gamerig_colors_lock']
            del armature['gamerig_colors_lock']
        
        # if 'gamerig_theme_to_add' in armature:
        #     armature.gamerig.theme_to_add = armature['gamerig_theme_to_add']
        #     del armature['gamerig_theme_to_add']

        for pb in context.object.pose.bones:
            if 'gamerig_type' in pb:
                pb.gamerig.name = pb['gamerig_type']
                if 'gamerig_parameters' in pb:
                    for k, v in pb['gamerig_parameters'].items():
                        if k != 'name':
                            pb.gamerig[k] = v
                del pb['gamerig_type']
            if 'gamerig_parameters' in pb:
                del pb['gamerig_parameters']

        return {'FINISHED'}


### Registering ###

register, unregister = bpy.utils.register_classes_factory((
    AddBoneGroupsOperator,
    UseStandardColorsOperator,
    ApplySelectionColorsOperator,
    AddBoneGroupOperator,
    AddBoneGroupThemeOperator,
    RemoveBoneGroupOperator,
    RemoveAllBoneGroupOperator,
    InitLayerOperator,
    RevealUnlinkedWidgetOperator,
    # GenerateProgressOperator,
    GenerateOperator,
    AddSampleOperator,
    ToggleArmatureReferenceOperator,
    EncodeMetarigOperator,
    EncodeMetarigSampleOperator,
    EncodeWidgetOperator,
    RenameBatchOperator,
    MigrateOperator,
    BoneGroupsUIList,
    BoneGroupsSpecialsMenu,
    ArmaturePanel,
    BonePanel,
    UtilityPanel,
    DevToolsPanel,
    RenameBatchPanel,
))
