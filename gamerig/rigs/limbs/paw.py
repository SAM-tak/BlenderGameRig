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
from rna_prop_ui import rna_idprop_ui_create
from ...utils import connected_children_names, flip_bone, copy_bone, MetarigError
from ..widgets import create_paw_widget, create_ballsocket_widget
from .limb import *

class Rig(Limb):

    def __init__(self, obj, bone_name, metabone):
        super().__init__(obj, bone_name, metabone)
        self.footprint_bone = self.params.footprint_bone
        self.org_bones = ([bone_name] + connected_children_names(obj, bone_name))[:4]


    def generate(self, context):
        if len(self.org_bones) < 4:
            raise MetarigError("gamerig.limb.paw: rig '%s' have no enough length " % self.org_bones[0])
        
        return super().generate(self.create_paw, f"""
# IK/FK Snap Button
if is_selected( controls ):
    props = layout.operator(Paw_FK2IK.bl_idname, text='Snap FK->IK ({self.org_bones[0]})', icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = controls[5]
    props.thigh_ik = ik_final[0]
    props.shin_ik  = ik_final[1]
    props.foot_ik  = ik_target
    props.toe_ik   = controls[7]
    props = layout.operator(Paw_IK2FK.bl_idname, text='Snap IK->FK ({self.org_bones[0]})', icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = controls[5]
    props.thigh_ik = controls[0]
    props.foot_ik  = controls[6]
    props.mfoot_ik = ik_target
    props.toe_ik   = controls[8]
    props.mtoe_ik  = controls[7]
    props.pole_ik  = controls[1]
""")


    def create_paw(self, bones):
        org_bones = self.org_bones

        bones['ik']['ctrl']['terminal'] = []

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

        bones['ik']['heel'] = heel
        bones['ik']['mch_ik_socket'] = mch_ik_socket

        # Create toes mch bone
        toes_mch = get_bone_name( org_bones[3], 'mch' )
        toes_mch = copy_bone( self.obj, org_bones[3], toes_mch )

        eb[ toes_mch ].use_connect = False
        eb[ toes_mch ].parent      = eb[ ctrl ]

        bones['ik']['toes_mch'] = toes_mch

        bones['ik']['ctrl']['terminal'] += [ heel, toes_mch, ctrl ]

        return bones


    def postprocess(self, context):
        super().postprocess(reverse_ik_widget = True)

        bones = self.bones

        ctrl = bones['ik']['ctrl']['terminal'][-1]

        heel = bones['ik']['heel']
        mch_ik_socket = bones['ik']['mch_ik_socket']
        toes_mch = bones['ik']['toes_mch']

        org_bones = self.org_bones

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

        # Add IK Stretch property and driver
        self.setup_ik_stretch(bones, pb, pb[ctrl])
        
        # Add IK Follow property and driver
        self.setup_ik_follow(pb, pb[ctrl], mch_ik_socket)

        # Create paw widget
        create_paw_widget(self.obj, ctrl)

        # Add ballsocket widget to heel
        create_ballsocket_widget(self.obj, heel)

        if len( org_bones ) >= 4:
            # Constrain toe bone to toes_mch
            self.make_constraint(org_bones[3], {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : toes_mch
            })

            pb_master = pb[ bones['fk']['ctrl'][0] ]

            # Find IK/FK switch property
            rna_idprop_ui_create( pb_master, 'IK/FK', default=0.0, overridable=True )

            # Add driver to limit scale constraint influence
            b        = org_bones[3]
            drv      = pb[b].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_fk_switch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '["IK/FK"]'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0


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
            """ Matches the fk bones in a leg rig to the ik bones.
            """
            obj = context.active_object

            thigh  = obj.pose.bones[self.thigh_fk]
            shin   = obj.pose.bones[self.shin_fk]
            foot   = obj.pose.bones[self.foot_fk]
            toe    = obj.pose.bones[self.toe_fk]
            
            thighi = obj.pose.bones[self.thigh_ik]
            shini  = obj.pose.bones[self.shin_ik]
            footi  = obj.pose.bones[self.foot_ik]
            toei   = obj.pose.bones[self.toe_ik]

            # Thigh position
            match_pose_translation(thigh, thighi)
            match_pose_rotation(thigh, thighi)
            match_pose_scale(thigh, thighi)
            insert_keyframe_by_mode(context, thigh)

            # Shin position
            match_pose_rotation(shin, shini)
            match_pose_scale(shin, shini)
            insert_keyframe_by_mode(context, shin)

            # Foot position
            match_pose_rotation(foot, footi)
            match_pose_scale(foot, footi)
            insert_keyframe_by_mode(context, foot)

            # Toe position
            match_pose_rotation(toe, toei)
            match_pose_scale(toe, toei)
            insert_keyframe_by_mode(context, toe)
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
    foot_ik  : bpy.props.StringProperty(name="Foot IK Name")
    mfoot_ik : bpy.props.StringProperty(name="MFoot IK Name")
    toe_ik   : bpy.props.StringProperty(name="Toe IK Name")
    mtoe_ik  : bpy.props.StringProperty(name="MToe IK Name")
    pole_ik  : bpy.props.StringProperty(name="Pole IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            """ Matches the ik bones in a leg rig to the fk bones.
            """
            obj = context.active_object

            thigh    = obj.pose.bones[self.thigh_fk]
            shin     = obj.pose.bones[self.shin_fk]
            foot     = obj.pose.bones[self.foot_fk]
            toe      = obj.pose.bones[self.toe_fk]

            if self.thigh_ik in obj.pose.bones:
                thighi = obj.pose.bones[self.thigh_ik]
            footi    = obj.pose.bones[self.foot_ik]
            mfooti   = obj.pose.bones[self.mfoot_ik]
            toei     = obj.pose.bones[self.toe_ik]
            mtoei    = obj.pose.bones[self.mtoe_ik]
            if self.pole_ik in obj.pose.bones:
                polei = obj.pose.bones[self.pole_ik]
            
            # Toe position
            mat = mtoei.bone.matrix_local.inverted() @ toei.bone.matrix_local
            toemat = get_pose_matrix_in_other_space(toe.matrix, toei) @ mat
            set_pose_translation(toei, toemat)
            set_pose_rotation(toei, toemat)
            set_pose_scale(toei, toemat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, toei)

            # Foot position
            mat = mfooti.bone.matrix_local.inverted() @ footi.bone.matrix_local
            footmat = get_pose_matrix_in_other_space(foot.matrix, footi) @ mat
            set_pose_translation(footi, footmat)
            set_pose_rotation(footi, footmat)
            set_pose_scale(footi, footmat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, footi)

            # Thigh position
            if self.thigh_ik in obj.pose.bones:
                match_pose_translation(thighi, thigh)
                match_pose_rotation(thighi, thigh)
                match_pose_scale(thighi, thigh)
                insert_keyframe_by_mode(context, thighi)
            
            # Pole direction
            if self.pole_ik in obj.pose.bones:
                polei = obj.pose.bones[self.pole_ik]
                match_pole_direction(context, polei, thigh, shin, foot)
                insert_keyframe_by_mode(context, polei)
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
