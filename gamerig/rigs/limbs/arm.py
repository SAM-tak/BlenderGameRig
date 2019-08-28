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
from ...utils import MetarigError, copy_bone
from ..widgets import create_hand_widget
from .limb import *

class Rig(Limb):

    def __init__(self, obj, bone_name, params):
        super().__init__(obj, bone_name, params)
        self.limb_type = 'arm' # TODO: remove it
        self.org_bones = list([bone_name] + connected_children_names(obj, bone_name))[:3]


    def generate(self, context):
        return super().generate(self.create_arm, """
controls = [%s]
ik_ctrl  = [%s]
fk_ctrl  = '%s'
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["IK/FK"]', text='IK/FK (' + fk_ctrl + ')', slider = True )
    props = layout.operator(Arm_FK2IK.bl_idname, text="Snap FK->IK (" + fk_ctrl + ")", icon='SNAP_ON')
    props.uarm_fk = controls[1]
    props.farm_fk = controls[2]
    props.hand_fk = controls[3]
    props.uarm_ik = controls[0]
    props.farm_ik = ik_ctrl[1]
    props.hand_ik = controls[4]
    props = layout.operator(Arm_IK2FK.bl_idname, text="Snap IK->FK (" + fk_ctrl + ")", icon='SNAP_ON')
    props.uarm_fk = controls[1]
    props.farm_fk = controls[2]
    props.hand_fk = controls[3]
    props.uarm_ik = controls[0]
    props.farm_ik = ik_ctrl[1]
    props.hand_ik = controls[4]

# FK limb follow
if is_selected( fk_ctrl ):
    layout.prop( pose_bones[ parent ], '["FK Limb Follow"]', text='FK Limb Follow (' + fk_ctrl + ')', slider = True )
""")


    def create_arm(self, bones):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.obj.data.edit_bones

        ctrl = get_bone_name( org_bones[2], 'ctrl', 'ik' )

        # Create IK arm control
        ctrl = copy_bone( self.obj, org_bones[2], ctrl )

        # clear parent (so that gamerig will parent to root)
        eb[ ctrl ].parent      = None
        eb[ ctrl ].use_connect = False

        # Parent
        eb[ bones['ik']['mch_target'] ].parent      = eb[ ctrl ]
        eb[ bones['ik']['mch_target'] ].use_connect = False

        # add IK Follow feature
        mch_ik_socket = self.make_ik_follow_bone(eb, ctrl)

        # Set up constraints
        # Constrain mch target bone to the ik control and mch stretch

        self.make_constraint(bones['ik']['mch_target'], {
            'constraint'  : 'COPY_LOCATION',
            'subtarget'   : bones['ik']['mch_str'],
            'head_tail'   : 1.0
        })

        # Constrain mch ik stretch bone to the ik control
        self.make_constraint(bones['ik']['mch_str'], {
            'constraint'  : 'DAMPED_TRACK',
            'subtarget'   : ctrl,
        })
        self.make_constraint(bones['ik']['mch_str'], {
            'constraint'  : 'STRETCH_TO',
            'subtarget'   : ctrl,
        })

        pb = self.obj.pose.bones

        # Modify rotation mode for ik and tweak controls
        pb[bones['ik']['ctrl']['limb']].rotation_mode = 'ZXY'

        pb_master = pb[ bones['fk']['ctrl'][0] ]

        # Add IK Stretch property and driver
        self.setup_ik_stretch(bones, pb, pb_master)
            
        # Add IK Follow property and driver
        self.setup_ik_follow(pb, pb_master, mch_ik_socket)

        # Create hand widget
        create_hand_widget(self.obj, ctrl)

        bones['ik']['ctrl']['terminal'] = [ ctrl ]

        return bones


def operator_script(rig_id):
    return '''
class Arm_FK2IK(bpy.types.Operator):
    """ Snaps an FK arm to an IK arm.
    """
    bl_idname = "gamerig.arm_fk2ik_{rig_id}"
    bl_label = "Snap FK arm to IK"
    bl_description = "Snap FK arm controllers to IK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    uarm_fk : bpy.props.StringProperty(name="Upper Arm FK Name")
    farm_fk : bpy.props.StringProperty(name="Forerm FK Name")
    hand_fk : bpy.props.StringProperty(name="Hand FK Name")

    uarm_ik : bpy.props.StringProperty(name="Upper Arm IK Name")
    farm_ik : bpy.props.StringProperty(name="Forearm IK Name")
    hand_ik : bpy.props.StringProperty(name="Hand IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            """ Matches the fk bones in an arm rig to the ik bones.
            """
            obj = context.active_object

            uarm  = obj.pose.bones[self.uarm_fk]
            farm  = obj.pose.bones[self.farm_fk]
            hand  = obj.pose.bones[self.hand_fk]
            uarmi = obj.pose.bones[self.uarm_ik]
            farmi = obj.pose.bones[self.farm_ik]
            handi = obj.pose.bones[self.hand_ik]

            # Upper arm position
            match_pose_translation(uarm, uarmi)
            match_pose_rotation(uarm, uarmi)
            match_pose_scale(uarm, uarmi)

            # Forearm position
            match_pose_translation(hand, handi)
            match_pose_rotation(farm, farmi)
            match_pose_scale(farm, farmi)

            # Hand position
            match_pose_translation(hand, handi)
            match_pose_rotation(hand, handi)
            match_pose_scale(hand, handi)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Arm_IK2FK(bpy.types.Operator):
    """ Snaps an IK arm to an FK arm.
    """
    bl_idname = "gamerig.arm_ik2fk_{rig_id}"
    bl_label = "Snap IK arm to FK"
    bl_description = "Snap IK arm controllers to FK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    uarm_fk : bpy.props.StringProperty(name="Upper Arm FK Name")
    farm_fk : bpy.props.StringProperty(name="Forerm FK Name")
    hand_fk : bpy.props.StringProperty(name="Hand FK Name")

    uarm_ik : bpy.props.StringProperty(name="Upper Arm IK Name")
    farm_ik : bpy.props.StringProperty(name="Forearm IK Name")
    hand_ik : bpy.props.StringProperty(name="Hand IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            """ Matches the ik bones in an arm rig to the fk bones.
            """
            obj = context.active_object

            uarm  = obj.pose.bones[self.uarm_fk]
            hand  = obj.pose.bones[self.hand_fk]
            uarmi = obj.pose.bones[self.uarm_ik]
            handi = obj.pose.bones[self.hand_ik]

            # Hand position
            match_pose_translation(handi, hand)
            match_pose_rotation(handi, hand)
            match_pose_scale(handi, hand)

            # Upper Arm position
            match_pose_translation(uarmi, uarm)
            match_pose_rotation(uarmi, uarm)
            match_pose_scale(uarmi, uarm)

            # Rotation Correction
            correct_rotation(uarmi, uarm)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


register_class(Arm_FK2IK)
register_class(Arm_IK2FK)


'''.format(rig_id=rig_id)


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    Limb.add_parameters(params)


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""
    Limb.parameters_ui(layout, params)


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('ORG-upper_arm.L')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.2588, 0.0148, 0.0000
    bone.roll = 1.5232
    bone.use_connect = False
    bone.use_deform = True
    bones['ORG-upper_arm.L'] = bone.name
    bone = arm.edit_bones.new('ORG-forearm.L')
    bone.head[:] = 0.2588, 0.0148, 0.0000
    bone.tail[:] = 0.4940, 0.0000, 0.0000
    bone.roll = 1.5232
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-upper_arm.L']]
    bones['ORG-forearm.L'] = bone.name
    bone = arm.edit_bones.new('ORG-hand.L')
    bone.head[:] = 0.4940, 0.0000, 0.0000
    bone.tail[:] = 0.5657, 0.0000, 0.0000
    bone.roll = -3.1196
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-forearm.L']]
    bones['ORG-hand.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['ORG-upper_arm.L']]
    pbone.gamerig_type = 'limbs.arm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.fk_layers = [False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.allow_ik_stretch = True
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['ORG-forearm.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ORG-hand.L']]
    pbone.gamerig_type = ''
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
