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
from ...utils import MetarigError, connected_children_names, copy_bone, put_bone, flip_bone, ctrlname
from ..widgets import create_foot_widget, create_ballsocket_widget, create_toe_widget, create_circle_widget
from .limb import *

class Rig(Limb):

    def __init__(self, obj, bone_name, metabone):
        super().__init__(obj, bone_name, metabone)
        self.footprint_bone = self.params.footprint_bone
        self.conntact_bone = self.params.conntact_bone if self.params.has_conntact_bone else None
        self.org_bones = ([bone_name] + connected_children_names(obj, bone_name))[:4]


    def generate(self, context):
        return super().generate(self.create_leg, """
controls = [%s]
ik_ctrls = [%s]
fk_ctrls = [%s]
ik_mchs  = [%s]
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["IK/FK"]', text='IK/FK (' + parent + ')', slider = True )
    props = layout.operator(Leg_FK2IK.bl_idname, text="Snap FK->IK (" + parent + ")", icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = ''
    props.thigh_ik = ik_ctrls[0]
    props.shin_ik  = ik_mchs[0]
    props.foot_ik  = ik_mchs[1]
    props.toe_ik   = ''
    props = layout.operator(Leg_IK2FK.bl_idname, text="Snap IK->FK (" + parent + ")", icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = ''
    props.thigh_ik = ik_ctrls[0]
    props.shin_ik  = ik_mchs[0]
    props.foot_ik  = controls[8]
    props.footroll = controls[7]
    props.mfoot_ik = ik_mchs[1]
    props.toe_ik   = ''

# IK Pole Mode
if is_selected( ik_ctrls ):
    layout.prop( pose_bones[ controls[1] ], '["IK Pole Mode"]', text='IK Pole Mode (' + parent + ')' )

# IK Toe Follow
if controls[1]['IK Pole Mode'] > 0 and is_selected( ik_ctrls ):
    layout.prop( pose_bones[ controls[1] ], '["IK Toe Follow"]', text='IK Toe Follow (' + parent + ')', slider = True )

# FK limb follow
if is_selected( fk_ctrls ):
    layout.prop( pose_bones[ parent ], '["FK Limb Follow"]', text='FK Limb Follow (' + parent + ')', slider = True )
""" if len(self.org_bones) < 4 else """
controls = [%s]
ik_ctrls = [%s]
fk_ctrls = [%s]
ik_mchs  = [%s]
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["IK/FK"]', text='IK/FK (' + parent + ')', slider = True )
    props = layout.operator(Leg_FK2IK.bl_idname, text="Snap FK->IK (" + parent + ")", icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = controls[5]
    props.thigh_ik = ik_ctrls[0]
    props.shin_ik  = ik_mchs[0]
    props.foot_ik  = ik_mchs[1]
    props.toe_ik   = controls[6]
    props = layout.operator(Leg_IK2FK.bl_idname, text="Snap IK->FK (" + parent + ")", icon='SNAP_ON')
    props.thigh_fk = controls[2]
    props.shin_fk  = controls[3]
    props.foot_fk  = controls[4]
    props.toe_fk   = controls[5]
    props.thigh_ik = ik_ctrls[0]
    props.shin_ik  = ik_mchs[0]
    props.foot_ik  = controls[8]
    props.footroll = controls[7]
    props.mfoot_ik = ik_mchs[1]
    props.toe_ik   = controls[6]

# IK Pole Mode
if is_selected( ik_ctrls ):
    layout.prop( pose_bones[ controls[1] ], '["IK Pole Mode"]', text='IK Pole Mode (' + controls[1] + ')' )

# IK Toe Follow
if pose_bones[ controls[1] ]['IK Pole Mode'] > 0 and is_selected( ik_ctrls ):
    layout.prop( pose_bones[ controls[1] ], '["IK Toe Follow"]', text='IK Toe Follow (' + controls[1] + ')', slider = True )

# FK limb follow
if is_selected( fk_ctrls ):
    layout.prop( pose_bones[ parent ], '["FK Limb Follow"]', text='FK Limb Follow (' + parent + ')', slider = True )
""", True)


    def create_leg( self, bones ):
        org_bones = self.org_bones

        bones['ik']['ctrl']['terminal'] = []

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
        eb[ heel ].align_roll(eb[ self.footprint_bone ].z_axis)
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

        eb[ bones['ik']['mch_ctrl_parent_target'] ].parent      = eb[ heel ]
        eb[ bones['ik']['mch_ctrl_parent_target'] ].use_connect = False

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
        roll2_mch = copy_bone( self.obj, org_bones[2], roll2_mch )

        eb[ roll2_mch ].use_connect = False
        eb[ roll2_mch ].parent      = None
        # align roll2_mch's height to horizontal
        eb[ roll2_mch ].tail.z = eb[ roll2_mch ].head.z
        eb[ roll2_mch ].align_roll(eb[ self.footprint_bone ].z_axis)

        put_bone(self.obj, roll2_mch, ( eb[ self.footprint_bone ].head + eb[ self.footprint_bone ].tail ) / 2)

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

        bones['ik']['roll1_mch'] = roll1_mch
        bones['ik']['roll2_mch'] = roll2_mch
        bones['ik']['rock1_mch'] = rock1_mch
        bones['ik']['rock2_mch'] = rock2_mch
        bones['ik']['heel'] = heel

        if len( org_bones ) >= 4:
            # Create toes control bone
            toeik = get_bone_name( org_bones[3], 'ctrl', 'ik' )
            toeik = copy_bone( self.obj, org_bones[3], toeik )

            eb[ toeik ].use_connect = False
            eb[ toeik ].parent      = eb[ roll2_mch ]

            bones['ik']['toe'] = toeik

            bones['ik']['ctrl']['terminal'].append(toeik)

        bones['ik']['ctrl']['terminal'] += [ heel, ctrl ]

        # add IK Follow feature
        mch_ik_socket = self.make_ik_follow_bone( eb, ctrl )
        bones['ik']['mch_ik_socket'] = mch_ik_socket

        if self.conntact_bone:
            # add contact bone mechanism
            contact_mch_ik = get_bone_name( self.conntact_bone, 'mch', 'ik' )
            contact_mch_ik = copy_bone( self.obj, self.conntact_bone, contact_mch_ik )
            eb[ contact_mch_ik ].use_connect = False
            eb[ contact_mch_ik ].parent = eb[ ctrl ]
            contact_mch_fk = get_bone_name( self.conntact_bone, 'mch', 'fk' )
            contact_mch_fk = copy_bone( self.obj, self.conntact_bone, contact_mch_fk )

            contact_ctrl = copy_bone( self.obj, self.conntact_bone, ctrlname(self.conntact_bone) )
            eb[ contact_ctrl ].use_connect = False
            eb[ contact_ctrl ].parent = eb[ contact_mch_fk ]

            bones['contact'] = {}
            bones['contact']['ik_mch'] = contact_mch_ik
            bones['contact']['fk_mch'] = contact_mch_fk
            bones['contact']['ctrl'] = contact_ctrl
            bones['ik']['ctrl']['additional'] += [contact_ctrl]

        return bones


    def postprocess(self, context):
        super().postprocess()

        bones = self.bones
        
        ctrl = bones['ik']['ctrl']['terminal'][-1]

        roll1_mch = bones['ik']['roll1_mch']
        roll2_mch = bones['ik']['roll2_mch']
        rock1_mch = bones['ik']['rock1_mch']
        rock2_mch = bones['ik']['rock2_mch']
        heel = bones['ik']['heel']
        mch_ik_socket = bones['ik']['mch_ik_socket']

        org_bones = self.org_bones
        pb = self.obj.pose.bones
        
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
            'invert_x'     : True,
            'owner_space'  : 'LOCAL',
            'target_space' : 'LOCAL'
        })
        self.make_constraint(roll2_mch, {
            'constraint'  : 'LIMIT_ROTATION',
            'use_limit_x' : True,
            'max_x'       : math.radians(360),
            'owner_space' : 'LOCAL'
        })

        # Constrain Ik controller parent
        mch_ctrl_parent = bones['ik']['mch_ctrl_parent']
        self.make_constraint(mch_ctrl_parent, {
            'constraint'   : 'COPY_ROTATION',
            'subtarget'    : bones['ik']['mch_ctrl_parent_target'],
            'use_x'        : False,
            'use_y'        : False,
            'owner_space'  : 'POSE',
            'target_space' : 'POSE'
        })

        self.make_constraint(mch_ctrl_parent, {
            'constraint'   : 'LIMIT_ROTATION',
            'use_limit_x'  : True,
            'use_limit_y'  : True,
            'owner_space' : 'LOCAL'
        })
        
        # Find IK toe follow property
        ik_dir_ctrl = bones['ik']['ctrl']['limb'][1]
        pb[ik_dir_ctrl]['IK Toe Follow']  = 1.0
        prop = rna_idprop_ui_prop_get( pb[ik_dir_ctrl], 'IK Toe Follow', create=True )
        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'Rate of facing knee to toe forward'
        # Add driver to limit scale constraint influence
        drv      = pb[mch_ctrl_parent].constraints[-1].driver_add("influence").driver
        drv.type = 'SUM'

        var = drv.variables.new()
        var.name = 'ik_toe_follow'
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[ik_dir_ctrl].path_from_id() + '['+ '"' + prop.name + '"' + ']'

        drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

        drv_modifier.mode            = 'POLYNOMIAL'
        drv_modifier.poly_order      = 1
        drv_modifier.coefficients[0] = 0.0
        drv_modifier.coefficients[1] = 1.0
        
        self.make_constraint(bones['ik']['mch_ctrl_parent_target'], {
            'constraint'   : 'COPY_ROTATION',
            'subtarget'    : bones['ik']['mch_target'],
            'invert_y'     : True
        })

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

        pb_master = pb[ bones['fk']['ctrl'][0] ]

        # Add IK Stretch property and driver
        self.setup_ik_stretch(bones, pb, pb_master)
        
        # Add IK Follow property and driver
        self.setup_ik_follow(pb, pb_master, mch_ik_socket)

        # Create leg widget
        create_foot_widget(self.obj, ctrl)

        # Add ballsocket widget to heel
        create_ballsocket_widget(self.obj, heel)

        if len( org_bones ) >= 4:
            toeik = bones['ik']['toe']
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
        
        if self.conntact_bone:
            # Set contact bone constraints up
            contact_mch_ik = bones['contact']['ik_mch']
            contact_mch_fk = bones['contact']['fk_mch']
            contact_ctrl   = bones['contact']['ctrl']

            min_x = (pb[self.footprint_bone].head - pb[self.conntact_bone].head).x
            max_x = (pb[self.footprint_bone].tail - pb[self.conntact_bone].head).x
            if max_x < min_x:
                max_x, min_x = min_x, max_x
            min_z = -abs((pb[ctrl].tail - pb[self.conntact_bone].head).y)
            max_z = abs((pb[ctrl].head - pb[self.conntact_bone].head).y)
            if max_z < min_z:
                max_z, min_z = min_z, max_z

            x_width = max(abs(min_x), abs(max_x)) * 5.0
            z_width = max(abs(min_z), abs(max_z)) * 5.0

            self.make_constraint(contact_mch_ik, {
                'constraint'     : 'TRANSFORM',
                'subtarget'      : heel,
                'owner_space'    : 'LOCAL',
                'target_space'   : 'LOCAL',
                'map_from'       : 'ROTATION',
                'from_min_x_rot' : math.radians(-10.0),
                'from_max_x_rot' : math.radians(10.0),
                'from_min_y_rot' : math.radians(-45.0),
                'from_max_y_rot' : math.radians(45.0),
                'map_top'        : 'LOCATION',
                'map_to_x_from'  : 'Y',
                'to_min_x'       : -x_width,
                'to_max_x'       : x_width,
                'map_to_y_from'  : 'Z',
                'map_to_z_from'  : 'X',
                'to_min_z'       : -z_width,
                'to_max_z'       : z_width,
                'mix_mode'       : 'REPLACE',
            })
            self.make_constraint(contact_mch_ik, {
                'constraint'     : 'LIMIT_LOCATION',
                'use_min_x'      : True,
                'min_x'          : min_x,
                'use_min_z'      : True,
                'min_z'          : min_z,
                'use_max_x'      : True,
                'max_x'          : max_x,
                'use_max_z'      : True,
                'max_z'          : max_z,
                'owner_space'    : 'LOCAL',
            })

            self.make_constraint(contact_mch_fk, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : contact_mch_ik
            })

            drv      = pb[contact_mch_fk].constraints[-1].driver_add("influence").driver
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

            self.make_constraint(self.conntact_bone, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : contact_ctrl
            })

            # add widget
            create_circle_widget(self.obj, contact_ctrl, radius = 0.5)


def operator_script(rig_id):
    return '''
class Leg_FK2IK(bpy.types.Operator):
    """ Snaps an FK leg to an IK leg.
    """
    bl_idname = "gamerig.leg_fk2ik_{rig_id}"
    bl_label = "Snap FK leg to IK"
    bl_description = "Snap FK leg controllers to IK ones (no keying)"
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
            if self.toe_fk in obj.pose.bones:
                toe    = obj.pose.bones[self.toe_fk]
            
            thighi = obj.pose.bones[self.thigh_ik]
            shini  = obj.pose.bones[self.shin_ik]
            footi  = obj.pose.bones[self.foot_ik]
            if self.toe_ik in obj.pose.bones:
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
            if self.toe_fk in obj.pose.bones:
                match_pose_rotation(toe, toei)
                match_pose_scale(toe, toei)
                insert_keyframe_by_mode(context, toe)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Leg_IK2FK(bpy.types.Operator):
    """ Snaps an IK leg to an FK leg.
    """
    bl_idname = "gamerig.leg_ik2fk_{rig_id}"
    bl_label = "Snap IK leg to FK"
    bl_description = "Snap IK leg controllers to FK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    thigh_fk : bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  : bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  : bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   : bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik : bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  : bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  : bpy.props.StringProperty(name="Foot IK Name")
    footroll : bpy.props.StringProperty(name="Foot Roll Name")
    mfoot_ik : bpy.props.StringProperty(name="MFoot IK Name")
    toe_ik   : bpy.props.StringProperty(name="Toe IK Name")

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
            if self.toe_fk in obj.pose.bones:
                toe = obj.pose.bones[self.toe_fk]

            thighi   = obj.pose.bones[self.thigh_ik]
            shini    = obj.pose.bones[self.shin_ik]
            footi    = obj.pose.bones[self.foot_ik]
            footroll = obj.pose.bones[self.footroll]
            mfooti   = obj.pose.bones[self.mfoot_ik]
            if self.toe_ik in obj.pose.bones:
                toei = obj.pose.bones[self.toe_ik]
            
            # Clear footroll
            set_pose_rotation(footroll, Matrix())

            # Foot position
            mat = mfooti.bone.matrix_local.inverted() @ footi.bone.matrix_local
            footmat = get_pose_matrix_in_other_space(foot.matrix, footi) @ mat
            set_pose_translation(footi, footmat)
            set_pose_rotation(footi, footmat)
            set_pose_scale(footi, footmat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, footi)

            if self.toe_fk in obj.pose.bones:
                # Toe position
                match_pose_translation(toei, toe)
                match_pose_rotation(toei, toe)
                match_pose_scale(toei, toe)
                insert_keyframe_by_mode(context, toei)

            # Thigh position
            match_pose_translation(thighi, thigh)
            match_pose_rotation(thighi, thigh)
            match_pose_scale(thighi, thigh)
            # Rotation Correction
            correct_rotation(thighi,thigh)
            insert_keyframe_by_mode(context, thighi)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Leg_FK2IK)
classes.append(Leg_IK2FK)
    

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
    params.has_conntact_bone = bpy.props.BoolProperty(
        name="Enable Foot Contanct Bone Feature",
        description="Retain Foot Contanct Mechanism",
        default=False
    )
    params.conntact_bone = bpy.props.StringProperty(
        name="Foot Contanct Bone Name",
        description="Specify Foot Contanct Bone name",
        default="ground.L"
    )
    Limb.add_parameters(params)


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""
    r = layout.row()
    r.prop(params, "footprint_bone")
    r = layout.row()
    r.prop(params, "has_conntact_bone")
    if params.has_conntact_bone:
        r.prop(params, "conntact_bone")
    Limb.parameters_ui(layout, params)


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('thigh.L')
    bone.head[:] = 0.0000, -0.0039, 0.9470
    bone.tail[:] = 0.0000, -0.0310, 0.4738
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['thigh.L'] = bone.name
    bone = arm.edit_bones.new('shin.L')
    bone.head[:] = 0.0000, -0.0310, 0.4738
    bone.tail[:] = 0.0000, 0.0145, 0.0747
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['thigh.L']]
    bones['shin.L'] = bone.name
    bone = arm.edit_bones.new('foot.L')
    bone.head[:] = 0.0000, 0.0145, 0.0747
    bone.tail[:] = 0.0000, -0.0836, 0.0148
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['shin.L']]
    bones['foot.L'] = bone.name
    bone = arm.edit_bones.new('toe.L')
    bone.head[:] = 0.0000, -0.0836, 0.0148
    bone.tail[:] = 0.0000, -0.1437, 0.0143
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['foot.L']]
    bones['toe.L'] = bone.name
    bone = arm.edit_bones.new('JIG-heel.L')
    bone.head[:] = -0.0363, 0.0411, 0.0000
    bone.tail[:] = 0.0363, 0.0411, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = False
    bone.parent = arm.edit_bones[bones['foot.L']]
    bones['JIG-heel.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['thigh.L']]
    pbone.gamerig.name = 'limbs.leg'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.fk_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
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
        pbone.gamerig.footprint_bone = "JIG-heel.L"
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['shin.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['foot.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['toe.L']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['JIG-heel.L']]
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
