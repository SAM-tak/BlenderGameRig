import bpy
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    copy_bone, flip_bone, org, basename, connected_children_names,
    create_widget,
    MetarigError
)
from .widgets import create_sphere_widget, create_circle_widget

class Rig:

    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.params = params

        self.chain_length = params.chain_length
        self.stretchable = params.stretchable

        # Assign values to tweak layers props if opted by user
        if params.tweak_extra_layers:
            self.tweak_layers = list(params.tweak_layers)
        else:
            self.tweak_layers = None

        if self.chain_length < 2:
            raise MetarigError(
                "GAMERIG ERROR: invalid chain length : rig '%s'" % basename(bone_name)
            )
        
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)[:self.chain_length-1]

        if len(self.org_bones) <= 1:
            raise MetarigError(
                "GAMERIG ERROR: invalid rig structure : rig '%s'" % basename(bone_name)
            )


    def make_controls( self ):

        bpy.ops.object.mode_set(mode ='EDIT')
        org_bones = self.org_bones
        eb = self.obj.data.edit_bones

        ctrl_chain = []
        for i in range( len( org_bones ) ):
            name = org_bones[i]

            ctrl_bone = copy_bone(self.obj, name, basename(name))
            eb[ctrl_bone].use_connect = False
            flip_bone(self.obj, ctrl_bone)
            eb[ctrl_bone].length /= 4
            eb[ctrl_bone].parent = None

            ctrl_chain.append( ctrl_bone )

        # Make widgets
        bpy.ops.object.mode_set(mode ='OBJECT')

        for ctrl in ctrl_chain[:-1]:
            create_circle_widget(self.obj, ctrl)
        create_sphere_widget(self.obj, ctrl_chain[-1])

        return ctrl_chain


    def make_constraints( self, all_bones ):

        bpy.ops.object.mode_set(mode ='OBJECT')
        org_bones = self.org_bones
        pb        = self.obj.pose.bones

        # org bones' constraints
        ctrls = all_bones['control']

        # Create IK/FK switch property
        pb[ctrls[0]]['IK/FK'] = 1.0
        prop = rna_idprop_ui_prop_get( pb[ctrls[0]], 'IK/FK', create=True )
        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'IK/FK Switch'

        for org, ctrl in zip( org_bones, ctrls ):
            self.make_constraint( org, {
                'constraint'  : 'DAMPED_TRACK',
                'subtarget'   : ctrl,
            })

            if ctrl != ctrls[0]:
                drv = pb[org].constraints[-1].driver_add("influence").driver
                drv.type = 'AVERAGE'

                var = drv.variables.new()
                var.name = 'ik_fk_switch'
                var.type = "SINGLE_PROP"
                var.targets[0].id = self.obj
                var.targets[0].data_path = pb[ctrls[0]].path_from_id() + '['+ '"' + prop.name + '"' + ']'

            if self.stretchable:
                self.make_constraint( org, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : ctrl,
                })

                # Add driver to relevant constraint
                drv = pb[org].constraints[-1].driver_add("influence").driver
                drv.type = 'AVERAGE'

                var = drv.variables.new()
                var.name = 'ik_fk_switch'
                var.type = "SINGLE_PROP"
                var.targets[0].id = self.obj
                var.targets[0].data_path = pb[ctrls[0]].path_from_id() + '['+ '"' + prop.name + '"' + ']'

                self.make_constraint( org, {
                    'constraint'  : 'MAINTAIN_VOLUME'
                })
                pb[ org ].ik_stretch = 0.01

        self.make_constraint( org_bones[-1], {
            'constraint'  : 'IK',
            'subtarget'   : ctrls[-1],
            'chain_count' : self.chain_length,
            'use_stretch' : self.stretchable,
        })
        # Add driver to relevant constraint
        drv = pb[org_bones[-1]].constraints[-1].driver_add("influence").driver
        drv.type = 'AVERAGE'

        var = drv.variables.new()
        var.name = 'ik_fk_switch'
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[ctrls[0]].path_from_id() + '['+ '"' + prop.name + '"' + ']'

        drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

        drv_modifier.mode            = 'POLYNOMIAL'
        drv_modifier.poly_order      = 1
        drv_modifier.coefficients[0] = 1.0
        drv_modifier.coefficients[1] = -1.0

        if self.stretchable:
            self.make_constraint( org_bones[-1], {
                'constraint'  : 'MAINTAIN_VOLUME'
            })


    def make_constraint( self, bone, constraint ):
        bpy.ops.object.mode_set(mode = 'OBJECT')
        pb = self.obj.pose.bones

        owner_pb     = pb[bone]
        const        = owner_pb.constraints.new( constraint['constraint'] )

        constraint['target'] = self.obj

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            setattr( const, p, constraint[p] )


    def generate(self):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Creating all bones
        ctrl_chain  = self.make_controls()

        all_bones = {
            'control' : ctrl_chain,
        }

        self.make_constraints( all_bones )

        return ["""
controls = %s
orgs = %s

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ controls[0] ], '["IK/FK"]', text='IK/FK (' + controls[0] + ')', slider = True )
    props = layout.operator("pose.gamerig_tentacle_fk2ik_" + rig_id, text="Snap FK->IK (" + controls[0] + ")")
    props.fk_ctrls = '%%s' %% controls[:-1]
    props.org_bones = '%%s' %% orgs
""" % (ctrl_chain, self.org_bones[1:])]

def operator_script(rig_id):
    return '''
class Tentacle_FK2IK(bpy.types.Operator):
    """ Snaps an FK to IK.
    """
    bl_idname = "pose.gamerig_tentacle_fk2ik_{rig_id}"
    bl_label = "Snap FK controller to IK"
    bl_options = {{'UNDO'}}

    fk_ctrls = bpy.props.StringProperty(name="FK Bone names")
    org_bones = bpy.props.StringProperty(name="Original Bone names")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            """ Matches the fk bones in an arm rig to the ik bones.
            """
            obj = context.active_object

            fks  = eval(self.fk_ctrls)
            orgs = eval(self.org_bones)

            for fk, org in zip(fks, orgs):
                fkb = obj.pose.bones[fk]
                orgb = obj.pose.bones[org]
                match_pose_translation(fkb, orgb)
                match_pose_rotation(fkb, orgb)
                match_pose_scale(fkb, orgb)
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}

register_class(Tentacle_FK2IK)


'''.format(rig_id=rig_id)


def add_parameters(params):
    """ Add the parameters of this rig type to the
        GameRigParameters PropertyGroup
    """
    params.chain_length = bpy.props.IntProperty(
        name         = 'Chain Length',
        default      = 2,
        min          = 2,
        description  = 'Position of the torso control and pivot point'
    )

    params.stretchable = bpy.props.BoolProperty(
        name        = "Stretchable",
        default     = True,
        description = "Allow stretch to controllers"
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "chain_length")
    
    r = layout.row()
    r.prop(params, "stretchable")


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('ORG-Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.0000, 0.0000, 0.3333
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['ORG-Bone'] = bone.name

    bone = arm.edit_bones.new('ORG-Bone.001')
    bone.head[:] = 0.0000, 0.0000, 0.3333
    bone.tail[:] = 0.0000, 0.0000, 0.6667
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-Bone']]
    bones['ORG-Bone.001'] = bone.name

    bone = arm.edit_bones.new('ORG-Bone.002')
    bone.head[:] = 0.0000, 0.0000, 0.6667
    bone.tail[:] = 0.0000, 0.0000, 1.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ORG-Bone.001']]
    bones['ORG-Bone.002'] = bone.name
    
    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['ORG-Bone']]
    pbone.gamerig_type = 'tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig_parameters.chain_length = 3
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.stretchable = True
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['ORG-Bone.001']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ORG-Bone.002']]
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
