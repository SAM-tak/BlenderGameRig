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
import re
from rna_prop_ui import rna_idprop_ui_create
from ..utils import copy_bone, copy_attributes, ctrlname, mchname, bone_prop_link_driver, bone_props_ui_string, org_bone_props_ui_string
from .widgets import create_bone_widget, create_circle_widget, create_box_widget, create_sphere_widget

class Rig:
    """ A "copy" rig.  All it does is duplicate the original bone and
        constrain it.
        This is a control and deformation rig.

    """
    def __init__(self, obj, bone, metabone):
        """ Gather and validate data about the rig.
        """
        self.obj      = obj
        self.org_bone = bone
        self.metabone = metabone
        self.params   = metabone.gamerig

    def generate(self, _context):
        """ Generate the rig.
            Do NOT modify any of the original bones, except for adding constraints.
            The main armature should be selected and active before this is called.
        """
        # Make a control bone (copy of original).
        self.bone = copy_bone(self.obj, self.org_bone, ctrlname(self.org_bone))

        if self.behaves_as_offset():
            self.parent_bone = copy_bone(self.obj, self.org_bone, mchname(self.org_bone))
            self.obj.data.edit_bones[self.bone].use_connect = False
            self.obj.data.edit_bones[self.bone].parent = self.obj.data.edit_bones[self.parent_bone]

        if self.params.immidiate_custom_property_ui:
            props_ui_str = org_bone_props_ui_string(self.obj, self.org_bone)
        else:
            props_ui_str = bone_props_ui_string(self.obj, self.bone, self.org_bone)

        if self.has_physics() or props_ui_str:
            return f"""
if is_selected('{self.bone}'):
""" + (props_ui_str if props_ui_str else "") + (f"""
    # Rig/Phy Switch on all Control Bones
    layout.prop( pose_bones['{self.bone}'], '["Rig/Phy"]', text='Rig/Phy ({self.org_bone})', slider = True )
    props = layout.operator(Generic_Snap.bl_idname, text="Snap to Target ({self.org_bone})", icon='SNAP_ON')
    props.ctrl = control
    props.target  = "{self.org_bone}"
""" if self.has_physics() else "")


    def postprocess(self, context):
        pb = self.obj.pose.bones
        bone = self.bone

        # copy original bone lock state and rotation mode
        pb[bone].rotation_mode = pb[self.org_bone].rotation_mode
        pb[bone].lock_location = pb[self.org_bone].lock_location
        pb[bone].lock_rotation = tuple(pb[self.org_bone].lock_rotation)
        pb[bone].lock_rotation_w = pb[self.org_bone].lock_rotation_w
        pb[bone].lock_rotations_4d = pb[self.org_bone].lock_rotations_4d
        pb[bone].lock_location = tuple(pb[self.org_bone].lock_location)
        pb[bone].lock_scale = tuple(pb[self.org_bone].lock_scale)

        if self.has_physics():
            if not 'Rig/Phy' in pb[bone]:
                # Create Rig/Physics switch property
                pb[bone]['Rig/Phy'] = 0.0
                rna_idprop_ui_create( pb[bone], 'Rig/Phy', default=0.0, description='Rig/Phy Switch', overridable=True )
            
            stashed = self.stash_constraint()

            # Constrain the original bone.
            con = pb[self.org_bone].constraints.new('COPY_TRANSFORMS')
            con.name = "copy_transforms"
            con.target = self.obj
            con.subtarget = self.bone

            self.unstash_constraint(stashed)
            
            # Add driver to relevant constraint
            drv = pb[self.org_bone].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'rig_phy_switch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[bone].path_from_id() + '["Rig/Phy"]'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 0.0
            drv_modifier.coefficients[1] = 1.0
        else:
            if len(self.metabone.constraints) > 0:
                if hasattr(self, 'parent_bone'):
                    # Copy constraints to parent bone
                    self.transfer_constraint(self.parent_bone)
                else:
                    # Copy constraints to controller
                    self.transfer_constraint(self.bone)
            # Constrain the original bone.
            con = pb[self.org_bone].constraints.new('COPY_TRANSFORMS')
            con.name = "copy_transforms"
            con.target = self.obj
            con.subtarget = self.bone

        if not self.params.immidiate_custom_property_ui:
            # add driver linked to original custom properties
            bone_prop_link_driver(self.obj, self.bone, self.org_bone)

        # Create control widget
        if self.params.control_widget_type == 'Circle':
            create_circle_widget(self.obj, self.bone, radius = 0.5)
        elif self.params.control_widget_type == 'Box':
            create_box_widget(self.obj, self.bone)
        elif self.params.control_widget_type == 'Sphere':
            create_sphere_widget(self.obj, self.bone)
        else:
            create_bone_widget(self.obj, self.bone)


    def stash_constraint( self ):
        pb = self.obj.pose.bones[self.org_bone]
        stashed = []
        for i in pb.constraints:
            d = {}
            keys = dir(i)
            for key in keys:
                if not key.startswith("_") \
                and not key.startswith("error_") \
                and key != "group" \
                and key != "is_valid" \
                and key != "rna_type" \
                and key != "bl_rna":
                    try:
                        d[key] = getattr(i, key)
                    except AttributeError:
                        pass
            stashed.append(d)
        
        for i in pb.constraints:
            pb.constraints.remove(i)

        return stashed


    def unstash_constraint( self, stash ):
        pb = self.obj.pose.bones

        owner_pb = pb[self.org_bone]
        for i in stash:
            const    = owner_pb.constraints.new( i['type'] )
            for k, v in i.items():
                if k != "type":
                    try:
                        setattr(const, k, v)
                    except AttributeError:
                        pass


    def transfer_constraint( self, bone ):
        pb = self.obj.pose.bones

        src_bone = pb[self.org_bone]
        dst_bone = pb[bone]

        # Copy Constraints
        for con1 in src_bone.constraints:
            con2 = dst_bone.constraints.new(type=con1.type)
            copy_attributes(con1, con2)

        # Clear Source Constraints
        for con1 in src_bone.constraints:
            src_bone.constraints.remove(con1)

        # Change Drivers target
        if self.obj.animation_data:
            for drv in self.obj.animation_data.drivers:
                print(drv.data_path)
                if drv.data_path.startswith(f'pose.bones["{src_bone.name}"]'):
                    drv.data_path = drv.data_path.replace(f'pose.bones["{src_bone.name}"]', f'pose.bones["{dst_bone.name}"]')


    def has_physics( self ):
        return not self.params.no_physics_controller and len(self.metabone.constraints) > 0 and self.metabone.constraints[0].type == 'COPY_TRANSFORMS'


    def behaves_as_offset( self ):
        return len(self.metabone.constraints) > 0 and (self.params.no_physics_controller or self.metabone.constraints[0].type != 'COPY_TRANSFORMS') and self.params.constraint_offset_controller


def operator_script(rig_id):
    return '''
class Generic_Snap(bpy.types.Operator):
    """ Snaps an generic controller to Target Bone Position.
    """
    bl_idname = "gamerig.generic_snap_{rig_id}"
    bl_label = "Snap to Target"
    bl_description = "Snap generic controller to target bone position (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    ctrl   : bpy.props.StringProperty(name="Ctrl Bone name")
    target : bpy.props.StringProperty(name="Ctrl Target Bone name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        #context.preferences.edit.use_global_undo = False
        try:
            """ Matches the fk bones in an arm rig to the ik bones.
            """
            obj = context.active_object

            cb = obj.pose.bones[self.ctrl]
            tb = obj.pose.bones[self.target]
            match_pose_translation(cb, tb)
            match_pose_rotation(cb, tb)
            match_pose_scale(cb, tb)

            insert_keyframe_by_mode(context, cb)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Generic_Snap)


'''.format(rig_id=rig_id)

def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.control_widget_type = bpy.props.EnumProperty(
        name        = "Control Widget Type",
        default     = 'Frustum',
        description = "Choose a widget for the bone control",
        items = [('Frustum', 'Frustum', ''), ('Circle', 'Circle', ''), ('Box', 'Box', ''), ('Sphere', 'Sphere', '')]
    )
    params.constraint_offset_controller = bpy.props.BoolProperty(
        name        = "Offset Controller for Contrainted Bone",
        description = "Behave offset controller when metabone has been contrainted",
        default     = False
    )
    params.no_physics_controller = bpy.props.BoolProperty(
        name        = "Non Physics Controller",
        description = "No Physcis/Animation switch feature even if has copy transform constraint",
        default     = False
    )
    params.immidiate_custom_property_ui = bpy.props.BoolProperty(
        name        = "Immidiate Custom Property UI",
        default     = True,
        description = "Display Custom Property UI for original bone instead link by driver."
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "control_widget_type")
    r = layout.row()
    r.prop(params, "constraint_offset_controller")
    r = layout.row()
    r.prop(params, "no_physics_controller")
    r = layout.row()
    r.prop(params, "immidiate_custom_property_ui")


def create_sample(obj):
    """ Create a sample metarig for this rig type.
    """
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.0000, 0.0000, 0.2000
    bone.roll = 0.0000
    bone.use_connect = False
    bones['Bone'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bone']]
    pbone.gamerig.name = 'generic'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone
