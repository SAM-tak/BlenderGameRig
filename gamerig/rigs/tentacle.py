import bpy, re
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    copy_bone, flip_bone, org, mch, basename, children_names,
    create_widget,
    MetarigError
)
from .widgets import create_sphere_widget, create_cube_widget

def get_bone_name( name, btype, suffix = '' ):
    if btype == 'mch':
        name = mch( basename( name ) )
    elif btype == 'ctrl':
        name = basename( name )

    if suffix:
        # RE pattern match right or left parts
        # match the letter "L" (or "R"), followed by an optional dot (".")
        # and 0 or more digits at the end of the the string
        results = re.match( r'^(\S+)(\.\S+)$',  name )
        if results:
            bname, addition = results.groups()
            name = bname + "_" + suffix + addition
        else:
            name = name  + "_" + suffix

    return name

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
        
        self.org_bones = [bone_name] + children_names(obj, bone_name, self.chain_length)

        if len(self.org_bones) <= 1:
            raise MetarigError(
                "GAMERIG ERROR: invalid rig structure : rig '%s'" % basename(bone_name)
            )


    def make_controls( self ):

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        fk_ctrl_chain = []
        for name in self.org_bones:
            ctrl_bone = copy_bone(self.obj, name, get_bone_name(name, 'ctrl', 'fk'))
            eb[ctrl_bone].use_connect = False
            flip_bone(self.obj, ctrl_bone)
            eb[ctrl_bone].length /= 4
            eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

            fk_ctrl_chain.append( ctrl_bone )

        ik_ctrl_chain = []
        for name in [self.org_bones[0], self.org_bones[-1]]:
            ctrl_bone = copy_bone(self.obj, name, get_bone_name(name, 'ctrl', 'ik'))
            eb[ctrl_bone].use_connect = False
            flip_bone(self.obj, ctrl_bone)
            eb[ctrl_bone].length /= 4
            eb[ctrl_bone].parent = eb[name].parent if name == self.org_bones[0] else None

            ik_ctrl_chain.append( ctrl_bone )

        # Make widgets
        bpy.ops.object.mode_set(mode ='OBJECT')

        for ctrl in fk_ctrl_chain:
            create_sphere_widget(self.obj, ctrl)
        for ctrl in ik_ctrl_chain:
            create_cube_widget(self.obj, ctrl)

        return (fk_ctrl_chain, ik_ctrl_chain)


    def make_mchs( self ):

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        fk_chain = []
        for name in self.org_bones:
            mch_bone = copy_bone(self.obj, name, get_bone_name(name, 'mch', 'fk'))
            eb[mch_bone].parent = None
            fk_chain.append( mch_bone )

        mch_bone = copy_bone(self.obj, self.org_bones[-1], get_bone_name(self.org_bones[-1], 'mch', 'fk_term'))
        eb[mch_bone].parent = None
        flip_bone(self.obj, mch_bone)
        eb[mch_bone].length /= 4
        fk_chain.append( mch_bone )

        ik_chain = []
        for name in self.org_bones:
            mch_bone = copy_bone(self.obj, name, get_bone_name(name, 'mch', 'ik'))
            eb[mch_bone].parent = None
            ik_chain.append( mch_bone )

        mch_bone = copy_bone(self.obj, self.org_bones[-1], get_bone_name(self.org_bones[-1], 'mch', 'ik_term'))
        eb[mch_bone].parent = None
        flip_bone(self.obj, mch_bone)
        eb[mch_bone].length /= 4
        ik_chain.append( mch_bone )

        for i, name in enumerate(fk_chain):
            if i > 0:
                eb[name].parent = eb[fk_chain[i - 1]]
            else:
                eb[name].parent = eb[self.org_bones[0]].parent

        for i, name in enumerate(ik_chain):
            if i > 0:
                eb[name].parent = eb[ik_chain[i - 1]]
            else:
                eb[name].parent = eb[self.org_bones[0]].parent

        return (fk_chain, ik_chain)


    def make_constraints( self, context, all_bones ):

        bpy.ops.object.mode_set(mode ='OBJECT')
        org_bones = self.org_bones
        pb        = self.obj.pose.bones

        # org bones' constraints
        fk_ctrls = all_bones['fk_ctrls']
        ik_ctrls = all_bones['ik_ctrls']
        fk_chain = all_bones['fk_chain']
        ik_chain = all_bones['ik_chain']

        # Create IK/FK switch property
        pb[fk_ctrls[0]]['IK/FK'] = 1.0
        prop = rna_idprop_ui_prop_get( pb[fk_ctrls[0]], 'IK/FK', create=True )
        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'IK/FK Switch'

        # fk chain
        for mchb, ctrl in zip( fk_chain, fk_ctrls ):
            self.make_constraint( mchb, {
                'constraint'  : 'DAMPED_TRACK',
                'subtarget'   : ctrl,
            })

            if self.stretchable:
                self.make_constraint( mchb, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : ctrl,
                })

                self.make_constraint( mchb, {
                    'constraint'  : 'MAINTAIN_VOLUME'
                })
                pb[ mchb ].ik_stretch = 0.01

        # ik chain
        self.make_constraint( ik_chain[0], {
            'constraint'  : 'DAMPED_TRACK',
            'subtarget'   : ik_ctrls[0],
        })

        if self.stretchable:
            self.make_constraint( ik_chain[0], {
                'constraint'  : 'STRETCH_TO',
                'subtarget'   : ik_ctrls[0],
            })

            self.make_constraint( ik_chain[0], {
                'constraint'  : 'MAINTAIN_VOLUME'
            })
            pb[ ik_chain[0] ].ik_stretch = 0.01
        
        self.make_constraint( ik_chain[-2], {
            'constraint'  : 'IK',
            'subtarget'   : ik_ctrls[-1],
            'chain_count' : self.chain_length,
            'use_stretch' : self.stretchable,
        })

        # bind original bone
        for org, fkmch, ikmch in zip( org_bones, fk_chain, ik_chain ):
            stashed = self.stash_constraint(org)

            self.make_constraint( org, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : fkmch
            })
            self.make_constraint( org, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : ikmch
            })

            # Add driver to relevant constraint
            drv = pb[org].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_fk_switch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[fk_ctrls[0]].path_from_id() + '["IK/FK"]'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

            self.unstash_constraint( org, stashed )

            if len(pb[org].constraints) > 2:
                if not 'Rig/Phy' in pb[fk_ctrls[0]]:
                    # Create Rig/Physics switch property
                    pb[fk_ctrls[0]]['Rig/Phy'] = 0.0
                    prop = rna_idprop_ui_prop_get( pb[fk_ctrls[0]], 'Rig/Phy', create=True )
                    prop["min"]         = 0.0
                    prop["max"]         = 1.0
                    prop["soft_min"]    = 0.0
                    prop["soft_max"]    = 1.0
                    prop["description"] = 'Rig/Phy Switch'
                
                # Add driver to relevant constraint
                drv = pb[org].constraints[-1].driver_add("influence").driver
                drv.type = 'AVERAGE'

                var = drv.variables.new()
                var.name = 'rig_phy_switch'
                var.type = "SINGLE_PROP"
                var.targets[0].id = self.obj
                var.targets[0].data_path = pb[fk_ctrls[0]].path_from_id() + '["Rig/Phy"]'

                drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

                drv_modifier.mode            = 'POLYNOMIAL'
                drv_modifier.poly_order      = 1
                drv_modifier.coefficients[0] = 0.0
                drv_modifier.coefficients[1] = 1.0


    def stash_constraint( self, bone ):
        pb = self.obj.pose.bones[bone]
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


    def unstash_constraint( self, bone, stash ):
        pb = self.obj.pose.bones

        owner_pb = pb[bone]

        for i in stash:
            const    = owner_pb.constraints.new( i['type'] )
            for k, v in i.items():
                if k != "type":
                    try:
                        setattr(const, k, v)
                    except AttributeError:
                        pass


    def make_constraint( self, bone, constraint ):
        bpy.ops.object.mode_set(mode = 'OBJECT')
        pb = self.obj.pose.bones

        owner_pb = pb[bone]
        const    = owner_pb.constraints.new( constraint['constraint'] )

        constraint['target'] = self.obj

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            setattr( const, p, constraint[p] )


    def generate(self, context):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Creating all bones
        ctrls  = self.make_controls()
        mchs  = self.make_mchs()

        all_bones = {
            'fk_ctrls' : ctrls[0],
            'ik_ctrls' : ctrls[1],
            'fk_chain' : mchs[0],
            'ik_chain' : mchs[1],
        }

        self.make_constraints(context, all_bones)

        return ["""
controls = %s
orgs = %s

# IK/FK Switch on all Control Bones
if is_selected( controls ):
    layout.prop( pose_bones[ controls[0] ], '["IK/FK"]', text='IK/FK (' + controls[0] + ')', slider = True )
    if 'Rig/Phy' in pose_bones[ controls[0] ]:
        layout.prop( pose_bones[ controls[0] ], '["Rig/Phy"]', text='Rig/Phy (' + controls[0] + ')', slider = True )
    props = layout.operator("pose.gamerig_tentacle_fk2ik_" + rig_id, text="Snap FK->IK (" + controls[0] + ")")
    props.fk_ctrls = "%s"
    props.ik_chain = "%s"
    props = layout.operator("pose.gamerig_tentacle_ik2fk_" + rig_id, text="Snap IK->FK (" + controls[0] + ")")
    props.ik_ctrls = "%s"
    props.fk_chain = "%s"
""" % (ctrls[0] + ctrls[1], self.org_bones[1:], '%s' % ctrls[0], '%s' % mchs[1][1:], '%s' % ctrls[1], '%s' % [mchs[0][1], mchs[0][-1]])]

def operator_script(rig_id):
    return '''
class Tentacle_FK2IK(bpy.types.Operator):
    """ Snaps an FK to IK.
    """
    bl_idname = "pose.gamerig_tentacle_fk2ik_{rig_id}"
    bl_label = "Snap FK controller to IK"
    bl_options = {{'UNDO'}}

    fk_ctrls : bpy.props.StringProperty(name="FK Ctrl Bone names")
    ik_chain : bpy.props.StringProperty(name="IK Bone names")

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

            fks  = eval(self.fk_ctrls)
            iks  = eval(self.ik_chain)

            for fk, ik in zip(fks, iks):
                fkb = obj.pose.bones[fk]
                ikb = obj.pose.bones[ik]
                match_pose_translation(fkb, ikb)
                match_pose_rotation(fkb, ikb)
                match_pose_scale(fkb, ikb)
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}

class Tentacle_IK2FK(bpy.types.Operator):
    """ Snaps an IK to FK.
    """
    bl_idname = "pose.gamerig_tentacle_ik2fk_{rig_id}"
    bl_label = "Snap IK controller to FK"
    bl_options = {{'UNDO'}}

    ik_ctrls : bpy.props.StringProperty(name="IK Ctrl Bone names")
    fk_chain : bpy.props.StringProperty(name="FK Bone names")

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

            iks = eval(self.ik_ctrls)
            fks = eval(self.fk_chain)

            for ik, fk in zip(iks, fks):
                ikb = obj.pose.bones[ik]
                fkb = obj.pose.bones[fk]
                match_pose_translation(ikb, fkb)
                match_pose_rotation(ikb, fkb)
                match_pose_scale(ikb, fkb)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}

register_class(Tentacle_FK2IK)
register_class(Tentacle_IK2FK)


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
