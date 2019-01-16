script_arm = """
controls = [%s]
ik_ctrl  = [%s]
fk_ctrl  = '%s'
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["ik_fk_rate"]', text = 'IK/FK', slider = True )
    props = layout.operator("pose.gamerig_arm_fk2ik_" + rig_id, text="Snap FK->IK (" + fk_ctrl + ")")
    props.uarm_fk = controls[1]
    props.farm_fk = controls[2]
    props.hand_fk = controls[3]
    props.uarm_ik = controls[0]
    props.farm_ik = ik_ctrl[1]
    props.hand_ik = controls[4]
    props = layout.operator("pose.gamerig_arm_ik2fk_" + rig_id, text="Snap IK->FK (" + fk_ctrl + ")")
    props.uarm_fk = controls[1]
    props.farm_fk = controls[2]
    props.hand_fk = controls[3]
    props.uarm_ik = controls[0]
    props.farm_ik = ik_ctrl[1]
    props.hand_ik = controls[4]

# FK limb follow
if is_selected( fk_ctrl ):
    layout.prop( pose_bones[ parent ], '["fk_limb_follow"]', text = 'FK Limb Follow', slider = True )
"""

#                 0             1              2           3           4           5              6               7             8
#controls = ['thigh_ik.L', 'thigh_fk.L', 'shin_fk.L', 'foot_fk.L', 'toe_fk.L', 'toe_ik.L', 'foot_heel_ik.L', 'foot_ik.L', 'MCH-toe_fk.L']
#            'thigh_ik.L', 'thigh_fk.L', 'shin_fk.L', 'foot_fk.L', 'toe.L', 'foot_heel_ik.L', 'foot_ik.L', 'MCH-foot_fk.L'
#
# ['foot_ik.L', 'MCH-thigh_ik.L', 'MCH-thigh_ik_target.L']
# 'foot_ik.L', 'MCH-thigh_ik.L', 'MCH-thigh_ik_target.L'
script_leg = """
controls = [%s]
ik_ctrl  = [%s]
fk_ctrl  = '%s'
parent   = '%s'

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ parent ], '["ik_fk_rate"]', text = 'IK/FK', slider = True )
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
    layout.prop( pose_bones[ parent ], '["fk_limb_follow"]', text = 'FK Limb Follow', slider = True )

"""

script_ik_stretch = """
# IK Stretch on IK Control bone
if is_selected( ik_ctrl ):
    layout.prop( pose_bones[ parent ], '["ik_stretch"]', text = 'IK Stretch', slider = True )
"""

def create_script(bones, limb_type, allow_ik_stretch):
    # All ctrls have IK/FK switch
    controls =  [ bones['ik']['ctrl']['limb'] ] + bones['fk']['ctrl']
    controls += bones['ik']['ctrl']['terminal']

    controls_string = ", ".join(["'" + x + "'" for x in controls])

    # IK ctrl has IK stretch
    ik_ctrl = [ bones['ik']['ctrl']['terminal'][-1] ]
    ik_ctrl += [ bones['ik']['mch_ik'] ]
    ik_ctrl += [ bones['ik']['mch_target'] ]

    ik_ctrl_string = ", ".join(["'" + x + "'" for x in ik_ctrl])

    if limb_type == 'arm':
        code = script_arm % (
            controls_string,
            ik_ctrl_string,
            bones['fk']['ctrl'][0],
            bones['fk']['ctrl'][0]
        )

    elif limb_type == 'leg':
        code = script_leg % (
            controls_string,
            ik_ctrl_string,
            bones['fk']['ctrl'][0],
            bones['fk']['ctrl'][0]
        )

    elif limb_type == 'paw':
        code = script_leg % (
            controls_string,
            ik_ctrl_string,
            bones['fk']['ctrl'][0],
            bones['fk']['ctrl'][0]
        )

    if allow_ik_stretch:
        code += script_ik_stretch

    return code
