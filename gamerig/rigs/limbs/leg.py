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
import bpy, math
from rna_prop_ui import rna_idprop_ui_prop_get
from ...utils import MetarigError, connected_children_names, new_bone, copy_bone, put_bone, flip_bone
from ..widgets import create_foot_widget, create_ballsocket_widget, create_toe_widget
from .limb import *

class Rig(Limb):

    def __init__(self, obj, bone_name, params):
        super().__init__(obj, bone_name, params)
        self.footprint_bone = org(params.footprint_bone)
        self.org_bones = list([bone_name] + connected_children_names(obj, bone_name))[:4]


    def generate(self, context):
        return super().generate(self.create_leg, """
controls = [%s]
ik_ctrl  = [%s]
fk_ctrl  = '%s'
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["IK/FK"]', text='IK/FK (' + fk_ctrl + ')', slider = True )
    props = layout.operator("pose.gamerig_leg_fk2ik_" + rig_id, text="Snap FK->IK (" + fk_ctrl + ")")
    props.thigh_fk = controls[1]
    props.shin_fk  = controls[2]
    props.foot_fk  = controls[3]
    props.toe_fk   = controls[4]
    props.thigh_ik = controls[0]
    props.shin_ik  = ik_ctrl[1]
    props.foot_ik  = ik_ctrl[2]
    props.toe_ik   = controls[5]
    props = layout.operator("pose.gamerig_leg_ik2fk_" + rig_id, text="Snap IK->FK (" + fk_ctrl + ")")
    props.thigh_fk = controls[1]
    props.shin_fk  = controls[2]
    props.foot_fk  = controls[3]
    props.toe_fk   = controls[4]
    props.thigh_ik = controls[0]
    props.shin_ik  = ik_ctrl[1]
    props.foot_ik  = controls[7]
    props.footroll = controls[6]
    props.mfoot_ik = ik_ctrl[2]
    props.toe_ik   = controls[5]

# FK limb follow
if is_selected( fk_ctrl ):
    layout.prop( pose_bones[ parent ], '["FK Limb Follow"]', text='FK Limb Follow (' + fk_ctrl + ')', slider = True )
""")


    def create_leg( self, bones ):
        org_bones = list([self.org_bones[0]] + connected_children_names(self.obj, self.org_bones[0]))

        bones['ik']['ctrl']['terminal'] = []

        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.obj.data.edit_bones

        # Create IK leg control
        ctrl = get_bone_name( org_bones[2], 'ctrl', 'ik' )
        ctrl = copy_bone( self.obj, org_bones[2], ctrl )

        # clear parent (so that gamerig will parent to root)
        eb[ ctrl ].parent      = None
        eb[ ctrl ].use_connect = False

        # Create heel ctrl bone
        heel = get_bone_name( org_bones[2], 'ctrl', 'heel_ik' )
        heel = copy_bone( self.obj, org_bones[2], heel )
        self.orient_bone( eb[ heel ], 'y', 0.5 )
        eb[ heel ].length = eb[ org_bones[2] ].length / 2

        # Reset control position and orientation
        l = eb[ ctrl ].length
        self.orient_bone( eb[ ctrl ], 'y', reverse = True )
        eb[ ctrl ].length = l

        # Parent
        eb[ heel ].use_connect = False
        eb[ heel ].parent      = eb[ ctrl ]

        eb[ bones['ik']['mch_target'] ].parent      = eb[ heel ]
        eb[ bones['ik']['mch_target'] ].use_connect = False

        # Create foot mch rock and roll bones

        # roll1 MCH bone
        roll1_mch = get_bone_name( self.footprint_bone, 'mch', 'roll' )
        roll1_mch = copy_bone( self.obj, org_bones[2], roll1_mch )

        # clear parent
        eb[ roll1_mch ].use_connect = False
        eb[ roll1_mch ].parent      = None

        flip_bone( self.obj, roll1_mch )

        # Create 2nd roll mch, and two rock mch bones
        roll2_mch = get_bone_name( self.footprint_bone, 'mch', 'roll' )
        roll2_mch = copy_bone( self.obj, org_bones[3], roll2_mch )

        eb[ roll2_mch ].use_connect = False
        eb[ roll2_mch ].parent      = None

        put_bone(
            self.obj,
            roll2_mch,
            ( eb[ self.footprint_bone ].head + eb[ self.footprint_bone ].tail ) / 2
        )

        eb[ roll2_mch ].length /= 4

        # align ctrl's height to roll2_mch
        eb[ ctrl ].head.z = eb[ ctrl ].tail.z = eb[ roll2_mch ].center.z

        # Rock MCH bones
        rock1_mch = get_bone_name( self.footprint_bone, 'mch', 'rock' )
        rock1_mch = copy_bone( self.obj, self.footprint_bone, rock1_mch )

        eb[ rock1_mch ].use_connect = False
        eb[ rock1_mch ].parent      = None

        self.orient_bone( eb[ rock1_mch ], 'y', 1.0, reverse = True )
        eb[ rock1_mch ].length = eb[ self.footprint_bone ].length / 2

        rock2_mch = get_bone_name( self.footprint_bone, 'mch', 'rock' )
        rock2_mch = copy_bone( self.obj, self.footprint_bone, rock2_mch )

        eb[ rock2_mch ].use_connect = False
        eb[ rock2_mch ].parent      = None

        self.orient_bone( eb[ rock2_mch ], 'y', 1.0 )
        eb[ rock2_mch ].length = eb[ self.footprint_bone ].length / 2

        # Parent rock and roll MCH bones
        eb[ roll1_mch ].parent = eb[ roll2_mch ]
        eb[ roll2_mch ].parent = eb[ rock1_mch ]
        eb[ rock1_mch ].parent = eb[ rock2_mch ]
        eb[ rock2_mch ].parent = eb[ ctrl ]

        # add IK Follow feature
        mch_ik_socket = self.make_ik_follow_bone( eb, ctrl )

        # Constrain rock and roll MCH bones
        self.make_constraint(roll1_mch, {
            'constraint'   : 'COPY_ROTATION',
            'subtarget'    : heel,
            'owner_space'  : 'LOCAL',
            'target_space' : 'LOCAL'
        })
        self.make_constraint(roll1_mch, {
            'constraint'  : 'LIMIT_ROTATION',
            'use_limit_x' : True,
            'max_x'       : math.radians(360),
            'owner_space' : 'LOCAL'
        })
        self.make_constraint(roll2_mch, {
            'constraint'   : 'COPY_ROTATION',
            'subtarget'    : heel,
            'use_y'        : False,
            'use_z'        : False,
            'invert_x'     : False,
            'owner_space'  : 'LOCAL',
            'target_space' : 'LOCAL'
        })
        self.make_constraint(roll2_mch, {
            'constraint'  : 'LIMIT_ROTATION',
            'use_limit_x' : True,
            'min_x'       : math.radians(-360),
            'owner_space' : 'LOCAL'
        })

        pb = self.obj.pose.bones
        for i,b in enumerate([ rock1_mch, rock2_mch ]):
            head_tail = pb[b].head - pb[self.footprint_bone].head
            if '.L' in b:
                if not i:
                    min_y = 0
                    max_y = math.radians(360)
                else:
                    min_y = math.radians(-360)
                    max_y = 0
            else:
                if not i:
                    min_y = math.radians(-360)
                    max_y = 0
                else:
                    min_y = 0
                    max_y = math.radians(360)


            self.make_constraint(b, {
                'constraint'   : 'COPY_ROTATION',
                'subtarget'    : heel,
                'use_x'        : False,
                'use_z'        : False,
                'owner_space'  : 'LOCAL',
                'target_space' : 'LOCAL'
            })
            self.make_constraint(b, {
                'constraint'  : 'LIMIT_ROTATION',
                'use_limit_y' : True,
                'min_y'       : min_y,
                'max_y'       : max_y,
                'owner_space' : 'LOCAL'
            })

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
            'subtarget'   : roll1_mch,
            'head_tail'   : 1.0
        })
        self.make_constraint(bones['ik']['mch_str'], {
            'constraint'  : 'STRETCH_TO',
            'subtarget'   : roll1_mch,
            'head_tail'   : 1.0
        })

        # Modify rotation mode for ik and tweak controls
        pb[bones['ik']['ctrl']['limb']].rotation_mode = 'ZXY'

        pb_master = pb[ bones['fk']['ctrl'][0] ]

        # Add IK Stretch property and driver
        self.setup_ik_stretch(bones, pb, pb_master)
        
        # Add IK Follow property and driver
        self.setup_ik_follow(pb, pb_master, mch_ik_socket)

        # Create leg widget
        create_foot_widget(self.obj, ctrl)

        # Create heel ctrl locks
        pb[ heel ].lock_location = True, True, True
        pb[ heel ].lock_rotation = False, False, True
        pb[ heel ].lock_scale    = True, True, True

        # Add ballsocket widget to heel
        create_ballsocket_widget(self.obj, heel)

        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.obj.data.edit_bones

        if len( org_bones ) >= 4:
            # Create toes control bone
            toeik = get_bone_name( org_bones[3], 'ctrl', 'ik' )
            toeik = copy_bone( self.obj, org_bones[3], toeik )

            eb[ toeik ].use_connect = False
            eb[ toeik ].parent      = eb[ roll2_mch ]

            # Constrain toeik
            self.make_constraint(org_bones[3], {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : toeik
            })
            
            # Additional Constrain mch_target_ik
            self.make_constraint(bones['ik']['mch_target'], {
                'constraint'  : 'DAMPED_TRACK',
                'subtarget'   : toeik,
                'head_tail'   : 0.0
            })

            pb   = self.obj.pose.bones
            #pb[ toeik ].lock_location = True, True, True

            # Find IK/FK switch property
            prop = rna_idprop_ui_prop_get( pb_master, 'IK/FK' )

            # Add driver to limit scale constraint influence
            b        = org_bones[3]
            drv      = pb[b].constraints[-1].driver_add("influence").driver
            drv.type = 'SUM'

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

            # Create toe circle widget
            create_toe_widget(self.obj, toeik)

            bones['ik']['ctrl']['terminal'].append(toeik)

        bones['ik']['ctrl']['terminal'] += [ heel, ctrl ]

        return bones


def operator_script(rig_id):
    return '''
class Leg_FK2IK(bpy.types.Operator):
    """ Snaps an FK leg to an IK leg.
    """
    bl_idname = "pose.gamerig_leg_fk2ik_{rig_id}"
    bl_label = "Snap FK leg to IK"
    bl_options = {{'UNDO'}}

    thigh_fk = bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  = bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  = bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   = bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik = bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  = bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  = bpy.props.StringProperty(name="Foot IK Name")
    toe_ik   = bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
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

            # Shin position
            match_pose_rotation(shin, shini)
            match_pose_scale(shin, shini)

            # Foot position
            match_pose_rotation(foot, footi)
            match_pose_scale(foot, footi)

            # Toe position
            match_pose_rotation(toe, toei)
            match_pose_scale(toe, toei)
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Leg_IK2FK(bpy.types.Operator):
    """ Snaps an IK leg to an FK leg.
    """
    bl_idname = "pose.gamerig_leg_ik2fk_{rig_id}"
    bl_label = "Snap IK leg to FK"
    bl_options = {{'UNDO'}}

    thigh_fk = bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  = bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  = bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   = bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik = bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  = bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  = bpy.props.StringProperty(name="Foot IK Name")
    footroll = bpy.props.StringProperty(name="Foot Roll Name")
    mfoot_ik = bpy.props.StringProperty(name="MFoot IK Name")
    toe_ik   = bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            """ Matches the ik bones in a leg rig to the fk bones.
            """
            obj = context.active_object

            thigh    = obj.pose.bones[self.thigh_fk]
            shin     = obj.pose.bones[self.shin_fk]
            foot     = obj.pose.bones[self.foot_fk]
            toe      = obj.pose.bones[self.toe_fk]

            thighi   = obj.pose.bones[self.thigh_ik]
            shini    = obj.pose.bones[self.shin_ik]
            footi    = obj.pose.bones[self.foot_ik]
            footroll = obj.pose.bones[self.footroll]
            mfooti   = obj.pose.bones[self.mfoot_ik]
            toei     = obj.pose.bones[self.toe_ik]
            
            # Clear footroll
            set_pose_rotation(footroll, Matrix())

            # Foot position
            mat = mfooti.bone.matrix_local.inverted() * footi.bone.matrix_local
            footmat = get_pose_matrix_in_other_space(foot.matrix, footi) * mat
            set_pose_translation(footi, footmat)
            set_pose_rotation(footi, footmat)
            set_pose_scale(footi, footmat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')

            # Toe position
            match_pose_translation(toei, toe)
            match_pose_rotation(toei, toe)
            match_pose_scale(toei, toe)

            # Thigh position
            match_pose_translation(thighi, thigh)
            match_pose_rotation(thighi, thigh)
            match_pose_scale(thighi, thigh)

            # Rotation Correction
            correct_rotation(thighi,thigh)
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


for cl in (Leg_FK2IK, Leg_IK2FK):
    register_class(cl)


'''.format(rig_id=rig_id)


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        GameRigParameters PropertyGroup
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

    bone = arm.edit_bones.new('ORG-thigh.L')
    bone.head[:] = 0.0000, -0.0039, 0.9470
    bone.tail[:] = 0.0000, -0.0310, 0.4738
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['ORG-thigh.L'] = bone.name
    bone = arm.edit_bones.new('ORG-shin.L')
    bone.head[:] = 0.0000, -0.0310, 0.4738
    bone.tail[:] = 0.0000, 0.0145, 0.0747
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-thigh.L']]
    bones['ORG-shin.L'] = bone.name
    bone = arm.edit_bones.new('ORG-foot.L')
    bone.head[:] = 0.0000, 0.0145, 0.0747
    bone.tail[:] = 0.0000, -0.0836, 0.0148
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-shin.L']]
    bones['ORG-foot.L'] = bone.name
    bone = arm.edit_bones.new('ORG-toe.L')
    bone.head[:] = 0.0000, -0.0836, 0.0148
    bone.tail[:] = 0.0000, -0.1437, 0.0143
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-foot.L']]
    bones['ORG-toe.L'] = bone.name
    bone = arm.edit_bones.new('JIG-heel.L')
    bone.head[:] = -0.0363, 0.0411, 0.0000
    bone.tail[:] = 0.0363, 0.0411, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = False
    bone.parent = arm.edit_bones[bones['ORG-foot.L']]
    bones['JIG-heel.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['ORG-thigh.L']]
    pbone.gamerig_type = 'limbs.leg'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig_parameters.fk_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.allow_ik_stretch = True
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.footprint_bone = "JIG-heel.L"
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['ORG-shin.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ORG-foot.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ORG-toe.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['JIG-heel.L']]
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
