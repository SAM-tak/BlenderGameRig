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
from rna_prop_ui import rna_idprop_ui_prop_get
from ...utils import (
    connected_children_names,
    flip_bone, copy_bone,
    MetarigError
)
from ..widgets import create_paw_widget, create_ballsocket_widget, create_toe_widget
from .limb import *

class Rig(Limb):

    def __init__(self, obj, bone_name, params):
        super().__init__(obj, bone_name, params)
        self.footprint_bone = params.footprint_bone
        self.org_bones = list([bone_name] + connected_children_names(obj, bone_name))[:4]


    def generate(self, context):
        return super().generate(self.create_paw, """
controls = [%s]
ik_ctrl  = [%s]
fk_ctrl  = '%s'
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["IK/FK"]', text='IK/FK (' + fk_ctrl + ')', slider = True )
    props = layout.operator(Paw_FK2IK.bl_idname, text="Snap FK->IK (" + fk_ctrl + ")", icon='SNAP_ON')
    props.thigh_fk = controls[1]
    props.shin_fk  = controls[2]
    props.foot_fk  = controls[3]
    props.toe_fk   = controls[4]
    props.thigh_ik = controls[0]
    props.shin_ik  = ik_ctrl[1]
    props.foot_ik  = ik_ctrl[2]
    props.toe_ik   = controls[6]
    props = layout.operator(Paw_IK2FK.bl_idname, text="Snap IK->FK (" + fk_ctrl + ")", icon='SNAP_ON')
    props.thigh_fk = controls[1]
    props.shin_fk  = controls[2]
    props.foot_fk  = controls[3]
    props.toe_fk   = controls[4]
    props.thigh_ik = controls[0]
    props.shin_ik  = ik_ctrl[1]
    props.foot_ik  = controls[5]
    props.mfoot_ik = ik_ctrl[2]
    props.toe_ik   = ik_ctrl[0]
    props.mtoe_ik  = controls[6]

# FK limb follow
if is_selected( fk_ctrl ):
    layout.prop( pose_bones[ parent ], '["FK Limb Follow"]', text='FK Limb Follow (' + fk_ctrl + ')', slider = True )
""")


    def create_paw(self, bones):
        org_bones = [self.org_bones[0]] + connected_children_names(self.obj, self.org_bones[0])

        bones['ik']['ctrl']['terminal'] = []

        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.obj.data.edit_bones

        # Create IK paw control
        ctrl = get_bone_name( org_bones[3], 'ctrl', 'ik' )
        ctrl = copy_bone( self.obj, org_bones[3], ctrl )

        # clear parent (so that gamerig will parent to root)
        eb[ ctrl ].parent      = None
        eb[ ctrl ].use_connect = False

        # Create heel control bone
        heel = get_bone_name( org_bones[2], 'ctrl', 'heel_ik' )
        heel = copy_bone( self.obj, org_bones[2], heel )

        # clear parent
        eb[ heel ].parent      = None
        eb[ heel ].use_connect = False

        # Parent
        eb[ heel ].parent      = eb[ ctrl ]
        eb[ heel ].use_connect = False

        flip_bone( self.obj, heel )

        eb[ bones['ik']['mch_target'] ].parent      = eb[ heel ]
        eb[ bones['ik']['mch_target'] ].use_connect = False

        # Reset control position and orientation
        l = eb[ ctrl ].length
        self.orient_bone(eb[ ctrl ], 'y', reverse = True)
        eb[ ctrl ].length = l

        # align ctrl's height to roll2_mch
        eb[ ctrl ].head.z = eb[ ctrl ].tail.z = eb[ self.footprint_bone ].center.z

        # add IK Follow feature
        mch_ik_socket = self.make_ik_follow_bone( eb, ctrl )

        # Set up constraints
        # Constrain mch target bone to the ik control and mch stretch

        self.make_constraint(bones['ik']['mch_target'], {
            'constraint'  : 'COPY_LOCATION',
            'subtarget'   : bones['ik']['mch_str'],
            'head_tail'   : 1.0
        })

        # Constrain mch ik stretch bone to the ik control
        self.make_constraint( bones['ik']['mch_str'], {
            'constraint'  : 'DAMPED_TRACK',
            'subtarget'   : heel,
            'head_tail'   : 1.0
        })
        self.make_constraint( bones['ik']['mch_str'], {
            'constraint'  : 'STRETCH_TO',
            'subtarget'   : heel,
            'head_tail'   : 1.0
        })

        pb = self.obj.pose.bones

        # Modify rotation mode for ik and tweak controls
        pb[bones['ik']['ctrl']['limb']].rotation_mode = 'ZYX'

        pb_master = pb[ bones['fk']['ctrl'][0] ]

        # Add IK Stretch property and driver
        self.setup_ik_stretch(bones, pb, pb_master)
        
        # Add IK Follow property and driver
        self.setup_ik_follow(pb, pb_master, mch_ik_socket)

        # Create paw widget
        create_paw_widget(self.obj, ctrl)

        # Set heel ctrl locks and rotation mode
        pb[ heel ].lock_location = True, True, True
        pb[ heel ].rotation_mode = 'ZXY'

        # Add ballsocket widget to heel
        create_ballsocket_widget(self.obj, heel)

        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.obj.data.edit_bones

        if len( org_bones ) >= 4:
            # Create toes mch bone
            toes_mch = get_bone_name( org_bones[3], 'mch' )
            toes_mch = copy_bone( self.obj, org_bones[3], toes_mch )

            eb[ toes_mch ].use_connect = False
            eb[ toes_mch ].parent      = eb[ ctrl ]

            # Constrain toe bone to toes_mch
            self.make_constraint(org_bones[3], {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : toes_mch
            })

            # Find IK/FK switch property
            pb   = self.obj.pose.bones
            prop = rna_idprop_ui_prop_get( pb_master, 'IK/FK' )

            # Add driver to limit scale constraint influence
            b        = org_bones[3]
            drv      = pb[b].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_fk_switch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '['+ '"' + prop.name + '"' + ']'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

        bones['ik']['ctrl']['terminal'] += [ heel, toes_mch, ctrl ]

        return bones


def operator_script(rig_id):
    return '''
class Paw_FK2IK(bpy.types.Operator):
    """ Snaps an FK leg to an IK leg.
    """
    bl_idname = "gamerig.paw_fk2ik_{rig_id}"
    bl_label = "Snap FK paw to IK"
    bl_description = "Snap FK paw controllers to IK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    thigh_fk : bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  : bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  : bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   : bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik : bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  : bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  : bpy.props.StringProperty(name="Foot IK Name")
    toe_ik   : bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            fk2ik_paw(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.foot_fk, self.toe_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.toe_ik])
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Paw_IK2FK(bpy.types.Operator):
    """ Snaps an IK paw to an FK leg.
    """
    bl_idname = "gamerig.paw_ik2fk_{rig_id}"
    bl_label = "Snap IK paw to FK"
    bl_description = "Snap IK paw controllers to FK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    thigh_fk : bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  : bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  : bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   : bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik : bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  : bpy.props.StringProperty(name="Shin IK Name")
    mfoot_ik : bpy.props.StringProperty(name="MFoot IK Name")
    foot_ik  : bpy.props.StringProperty(name="Foot IK Name")
    mtoe_ik  : bpy.props.StringProperty(name="MToe IK Name")
    toe_ik   : bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            ik2fk_paw(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.foot_fk, self.toe_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.mfoot_ik, self.toe_ik, self.mtoe_ik])
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Paw_FK2IK)
classes.append(Paw_IK2FK)

'''.format(rig_id=rig_id)


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.footprint_bone = bpy.props.StringProperty(
        name="Footprint Bone Name",
        description="Specify footprint bone name",
        default="JIG-heel.L"
    )
    Limb.add_parameters(params)


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""
    r = layout.row()
    r.prop(params, "footprint_bone")
    Limb.parameters_ui(layout, params)


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('forelimb.01.L')
    bone.head[:] = 0.0000, 0.0000, 0.6649
    bone.tail[:] = -0.0000, 0.0572, 0.3784
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['forelimb.01.L'] = bone.name
    bone = arm.edit_bones.new('forelimb.02.L')
    bone.head[:] = -0.0000, 0.0572, 0.3784
    bone.tail[:] = -0.0000, 0.0000, 0.1024
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['forelimb.01.L']]
    bones['forelimb.02.L'] = bone.name
    bone = arm.edit_bones.new('forelimb.03.L')
    bone.head[:] = -0.0000, 0.0000, 0.1024
    bone.tail[:] = -0.0000, -0.0507, 0.0492
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['forelimb.02.L']]
    bones['forelimb.03.L'] = bone.name
    bone = arm.edit_bones.new('forepaw.L')
    bone.head[:] = -0.0000, -0.0507, 0.0492
    bone.tail[:] = 0.0000, -0.1405, 0.0227
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['forelimb.03.L']]
    bones['forepaw.L'] = bone.name
    bone = arm.edit_bones.new('JIG-forepawstamp.L')
    bone.head[:] = -0.0400, -0.0526, 0.0000
    bone.tail[:] = 0.0400, -0.0526, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['forelimb.03.L']]
    bones['JIG-forepawstamp.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['forelimb.01.L']]
    pbone.gamerig.name = 'limbs.paw'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.fk_layers = [False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig.tweak_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig.allow_ik_stretch = True
    except AttributeError:
        pass
    try:
        pbone.gamerig.footprint_bone = "JIG-forepawstamp.L"
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['forelimb.02.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forelimb.03.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forepaw.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['JIG-forepawstamp.L']]
    pbone.gamerig.name = ''
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
