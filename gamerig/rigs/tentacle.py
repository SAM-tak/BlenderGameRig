import bpy
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    copy_bone, flip_bone, ctrlname, mchname, basename, children_names,
    insert_before_first_period,
    create_widget,
    MetarigError
)
from .widgets import create_sphere_widget, create_cube_widget


class Rig:

    def __init__(self, obj, bone_name, metabone):
        self.obj = obj
        self.params = metabone.gamerig
        self.switchable_rig = len(metabone.constraints) > 0

        if self.params.chain_length < 2:
            raise MetarigError(
                "GAMERIG ERROR: invalid chain length : rig '%s'" % bone_name
            )
        
        self.org_bones = [bone_name] + children_names(obj, bone_name, self.params.chain_length - 1)

        if len(self.org_bones) <= 1:
            raise MetarigError(
                "GAMERIG ERROR: invalid rig structure : rig '%s'" % bone_name
            )

        if any([x > 0 and x < 2 for x in self.params.mid_ik_lens]):
            raise MetarigError(
                "GAMERIG ERROR: invalid mid ik chain length : rig '%s'" % bone_name
            )

        # Assign values to FK layers props if opted by user
        if self.params.fk_extra_layers:
            self.fk_layers = list(self.params.fk_layers)
        else:
            self.fk_layers = None


    def make_controls( self ):
        eb = self.obj.data.edit_bones

        fk_ctrl_chain = []

        for name in self.org_bones:
            ctrl_bone = copy_bone(self.obj, name, ctrlname(insert_before_first_period(name, '_fk')))
            eb[ctrl_bone].use_connect = False
            flip_bone(self.obj, ctrl_bone)
            eb[ctrl_bone].length /= 4
            eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

            fk_ctrl_chain.append( ctrl_bone )

        ik_ctrl_chain = []
        if not self.params.fk_only:
            ik_org_chain = []
            cur_ik_len = 0
            for i in self.params.mid_ik_lens:
                if i > 0:
                    ik_org_chain.append(self.org_bones[cur_ik_len])
                    ik_org_chain.append(self.org_bones[cur_ik_len + i - 1])
                    if cur_ik_len + i >= len(self.org_bones) - 2:
                        break
                    cur_ik_len += i
            
            if len(ik_org_chain) > 0:
                ik_org_chain.append(self.org_bones[cur_ik_len])
                ik_org_chain.append(self.org_bones[-1])
            else:
                ik_org_chain = [self.org_bones[0], self.org_bones[-1]]

            for i, name in enumerate(ik_org_chain):
                ctrl_bone = copy_bone(self.obj, name, ctrlname(insert_before_first_period(name, '_ik')))
                eb[ctrl_bone].use_connect = False
                flip_bone(self.obj, ctrl_bone)
                eb[ctrl_bone].length /= 4
                eb[ctrl_bone].parent = eb[name].parent if i == 0 else eb[ik_ctrl_chain[-1]] if i % 2 == 0 else None

                ik_ctrl_chain.append( ctrl_bone )

        root_ctrls = []
        if self.params.add_root_controller:
            name = self.org_bones[0]

            ctrl_bone = copy_bone(self.obj, name, ctrlname(insert_before_first_period(name, '_root_fk')))
            eb[ctrl_bone].use_connect = False
            eb[ctrl_bone].length /= 4
            eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

            root_ctrls.append( ctrl_bone )

            if not self.params.fk_only:
                ctrl_bone = copy_bone(self.obj, name, ctrlname(insert_before_first_period(name, '_root_ik')))
                eb[ctrl_bone].use_connect = False
                eb[ctrl_bone].length /= 4
                eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

                root_ctrls.append( ctrl_bone )

        return (fk_ctrl_chain, ik_ctrl_chain, root_ctrls)


    def make_mchs( self ):
        eb = self.obj.data.edit_bones

        fk_chain = []
        for name in self.org_bones:
            mch_bone = copy_bone(self.obj, name, mchname(insert_before_first_period(name, '_fk')))
            eb[mch_bone].parent = None
            fk_chain.append( mch_bone )

        mch_bone = copy_bone(self.obj, self.org_bones[-1], mchname(insert_before_first_period(name, '_fk_term')))
        eb[mch_bone].parent = None
        flip_bone(self.obj, mch_bone)
        eb[mch_bone].length /= 4
        fk_chain.append( mch_bone )

        ik_chain = []
        if not self.params.fk_only:
            for name in self.org_bones:
                mch_bone = copy_bone(self.obj, name, mchname(insert_before_first_period(name, '_ik')))
                eb[mch_bone].parent = None
                ik_chain.append( mch_bone )

        for i, name in enumerate(fk_chain):
            if i == 0:
                eb[name].parent = eb[self.org_bones[0]].parent
            else:
                eb[name].parent = eb[fk_chain[i - 1]]

        for i, name in enumerate(ik_chain):
            if i == 0:
                eb[name].parent = eb[self.org_bones[0]].parent
            else:
                eb[name].parent = eb[ik_chain[i - 1]]

        return (fk_chain, ik_chain)


    def make_constraints( self, context, all_bones ):

        org_bones = self.org_bones
        pb        = self.obj.pose.bones

        # org bones' constraints
        fk_ctrls = all_bones['fk_ctrls']
        ik_ctrls = all_bones['ik_ctrls']
        root_ctrls = all_bones['root_ctrls']
        fk_chain = all_bones['fk_chain']
        ik_chain = all_bones['ik_chain']

        # fk chain
        for mchb, ctrl in zip( fk_chain, fk_ctrls ):
            if self.params.add_root_controller and mchb == fk_chain[0]:
                self.make_constraint( mchb, {
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : root_ctrls[0],
                })
            
            self.make_constraint( mchb, {
                'constraint'  : 'DAMPED_TRACK',
                'subtarget'   : ctrl,
            })

            if self.params.stretchable:
                self.make_constraint( mchb, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : ctrl,
                })

                self.make_constraint( mchb, {
                    'constraint'  : 'MAINTAIN_VOLUME'
                })
                pb[ mchb ].ik_stretch = 0.01

        # ik chain
        if not self.params.fk_only:
            ik_chain_target = []
            ik_lens = []
            cur_ik_len = 0
            for i in self.params.mid_ik_lens:
                if i > 0:
                    if cur_ik_len + i >= len(self.org_bones) - 1:
                        break
                    ik_chain_target.append(ik_chain[cur_ik_len])
                    ik_chain_target.append(ik_chain[cur_ik_len + i - 1])
                    ik_lens.append(i)
                    cur_ik_len += i
            
            if len(ik_chain_target) > 0:
                ik_chain_target.append(ik_chain[cur_ik_len])
                ik_chain_target.append(ik_chain[-1])
                ik_lens.append(len(self.org_bones) - cur_ik_len)
            else:
                ik_chain_target = [ik_chain[0], ik_chain[-1]]
            
            if len(ik_lens) == 0:
                ik_lens.append(self.params.chain_length)
            
            for mchb, ctrl in zip( ik_chain_target[0::2], ik_ctrls[0::2] ):
                if self.params.add_root_controller and mchb == ik_chain_target[0]:
                    self.make_constraint( mchb, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : root_ctrls[1],
                    })
                
                self.make_constraint( mchb, {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : ctrl,
                })

                if self.params.stretchable:
                    self.make_constraint( mchb, {
                        'constraint'  : 'STRETCH_TO',
                        'subtarget'   : ctrl,
                    })


            for l, mchb, ctrl in zip( ik_lens, ik_chain_target[1::2], ik_ctrls[1::2] ):
                self.make_constraint( mchb, {
                    'constraint'  : 'IK',
                    'subtarget'   : ctrl,
                    'chain_count' : l,
                    'use_stretch' : self.params.stretchable,
                })

            if self.params.stretchable:
                for mchb in ik_chain:
                    pb[ mchb ].ik_stretch = 0.01

        # bind original bone
        for org, fkmch, ikmch in zip( org_bones, fk_chain, ik_chain if not self.params.fk_only else fk_chain ):
            stashed = self.stash_constraint(org)

            self.make_constraint( org, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : fkmch
            })
            
            if not self.params.fk_only:
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

            if self.switchable_rig:
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
        pb = self.obj.pose.bones

        owner_pb = pb[bone]
        const    = owner_pb.constraints.new( constraint['constraint'] )

        constraint['target'] = self.obj

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            setattr( const, p, constraint[p] )


    def generate(self, context):
        # Creating all bones
        self.ctrls  = self.make_controls()
        self.mchs  = self.make_mchs()

        ik_fk_snap_target = []
        cur_ik_len = 0
        for i in self.params.mid_ik_lens:
            if i > 0:
                if cur_ik_len + i >= len(self.org_bones) - 2:
                    break
                ik_fk_snap_target.append(self.mchs[0][cur_ik_len + 1])
                ik_fk_snap_target.append(self.mchs[0][cur_ik_len + i])
                cur_ik_len += i
        
        if len(ik_fk_snap_target) > 0:
            ik_fk_snap_target.append(self.mchs[0][cur_ik_len + 1])
            ik_fk_snap_target.append(self.mchs[0][-1])
        else:
            ik_fk_snap_target = [self.mchs[0][1], self.mchs[0][-1]]

        if self.params.fk_only and not self.switchable_rig:
            return ''
        else:
            return """
controls = %s

if is_selected( controls ):
""" % (self.ctrls[0] + self.ctrls[1] + self.ctrls[2]) + ("""
    # IK/FK Switch on all Control Bones
    layout.prop( pose_bones[ controls[0] ], '["IK/FK"]', text='IK/FK (' + controls[0] + ')', slider = True )
""" if not self.params.fk_only else '') + ("""
    layout.prop( pose_bones[ controls[0] ], '["Rig/Phy"]', text='Rig/Phy (' + controls[0] + ')', slider = True )
""" if self.switchable_rig else '') + ("""
    props = layout.operator(Tentacle_FK2IK.bl_idname, text="Snap FK->IK (" + controls[0] + ")", icon='SNAP_ON')
    props.fk_ctrls = "%s"
    props.ik_chain = "%s"
    props = layout.operator(Tentacle_IK2FK.bl_idname, text="Snap IK->FK (" + controls[0] + ")", icon='SNAP_ON')
    props.ik_ctrls = "%s"
    props.fk_chain = "%s"
""" % (self.ctrls[0], self.mchs[1][1:], self.ctrls[1], ik_fk_snap_target) if not self.params.fk_only else '') + ("""
    props = layout.operator(Tentacle_FK2Target.bl_idname, text="Snap FK->Target (" + controls[0] + ")", icon='SNAP_ON')
    props.fk_ctrls = "%s"
    props.targets  = "%s"
""" % (self.ctrls[0], self.org_bones[1:]) if self.switchable_rig else '')

    def postprocess(self, context):
        pb = self.obj.pose.bones

        # Make widgets
        for ctrl in self.ctrls[0]:
            if self.fk_layers:
                pb[ctrl].bone.layers = self.fk_layers
            create_sphere_widget(self.obj, ctrl)
        for ctrl in self.ctrls[1]:
            create_cube_widget(self.obj, ctrl)

        if self.params.add_root_controller:
            create_sphere_widget(self.obj, self.ctrls[2][0])
            if not self.params.fk_only:
                create_cube_widget(self.obj, self.ctrls[2][1])

        if not self.params.fk_only:
            # Create IK/FK switch property
            pb[self.ctrls[0][0]]['IK/FK'] = 1.0
            prop = rna_idprop_ui_prop_get( pb[self.ctrls[0][0]], 'IK/FK', create=True )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'IK/FK Switch'

        all_bones = {
            'fk_ctrls'   : self.ctrls[0],
            'ik_ctrls'   : self.ctrls[1],
            'root_ctrls' : self.ctrls[2],
            'fk_chain'   : self.mchs[0],
            'ik_chain'   : self.mchs[1],
        }

        self.make_constraints(context, all_bones)


def operator_script(rig_id):
    return '''
class Tentacle_FK2IK(bpy.types.Operator):
    """ Snaps an FK to IK.
    """
    bl_idname = "gamerig.tentacle_fk2ik_{rig_id}"
    bl_label = "Snap FK tentacle to IK"
    bl_description = "Snap FK tentacle controllers to IK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

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
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}

class Tentacle_IK2FK(bpy.types.Operator):
    """ Snaps an IK to FK.
    """
    bl_idname = "gamerig.tentacle_ik2fk_{rig_id}"
    bl_label = "Snap IK tentacle to FK"
    bl_description = "Snap IK tentacle controllers to FK ones (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    ik_ctrls : bpy.props.StringProperty(name="IK Ctrl Bone names")
    fk_chain : bpy.props.StringProperty(name="FK Bone names")

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


class Tentacle_FK2Target(bpy.types.Operator):
    """ Snaps an FK to Target Bone Position.
    """
    bl_idname = "gamerig.tentacle_fk2bone_{rig_id}"
    bl_label = "Snap FK tentacle to Target"
    bl_description = "Snap FK tentacle controllers to target bone position (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    fk_ctrls : bpy.props.StringProperty(name="FK Ctrl Bone names")
    targets  : bpy.props.StringProperty(name="Ctrl Target Bone names")

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
            targets  = eval(self.targets)

            for fk, target in zip(fks, targets):
                fkb = obj.pose.bones[fk]
                tb = obj.pose.bones[target]
                match_pose_translation(fkb, tb)
                match_pose_rotation(fkb, tb)
                match_pose_scale(fkb, tb)
            
            fkb = obj.pose.bones[fks[-1]]
            mat = get_pose_matrix_in_other_space(Matrix.Translation(tb.vector) @ tb.matrix, fkb)
            set_pose_translation(fkb, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            match_pose_rotation(fkb, tb)
            match_pose_scale(fkb, tb)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Tentacle_FK2IK)
classes.append(Tentacle_IK2FK)
classes.append(Tentacle_FK2Target)


'''.format(rig_id=rig_id)


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.chain_length = bpy.props.IntProperty(
        name         = 'Chain Length',
        default      = 2,
        min          = 2,
        description  = 'Length of Tentacle Rig Chain'
    )

    params.mid_ik_lens = bpy.props.IntVectorProperty(
        name         = 'Mid IK Chain Length',
        size         = 4,
        description  = 'Lengths of Intermediate IK chain'
    )

    params.stretchable = bpy.props.BoolProperty(
        name        = "Stretchable",
        default     = True,
        description = "Allow stretch to controllers"
    )

    params.fk_only = bpy.props.BoolProperty(
        name        = "FK Only",
        default     = False,
        description = "Don't make IK controllers."
    )

    params.add_root_controller = bpy.props.BoolProperty(
        name        = "Add Root Controller",
        default     = False,
        description = "Add controller for root position."
    )

    # Setting up extra layers for the FK
    params.fk_extra_layers = bpy.props.BoolProperty(
        name        = "FK Extra Layers",
        default     = True,
        description = "FK Extra Layers"
    )

    params.fk_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the FK controls to be on",
        default     = tuple( [ i == 1 for i in range(0, 32) ] )
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "chain_length")

    r = layout.row()
    r.prop(params, "mid_ik_lens")
    
    r = layout.row()
    r.prop(params, "stretchable")
    r.prop(params, "fk_only")
    r.prop(params, "add_root_controller")

    r = layout.row()
    r.prop(params, "fk_extra_layers")
    r.active = params.fk_extra_layers

    col = r.column(align=True)
    row = col.row(align=True)

    for i in range(8):
        row.prop(params, "fk_layers", index=i, toggle=True, text="")

    row = col.row(align=True)

    for i in range(16,24):
        row.prop(params, "fk_layers", index=i, toggle=True, text="")

    col = r.column(align=True)
    row = col.row(align=True)

    for i in range(8,16):
        row.prop(params, "fk_layers", index=i, toggle=True, text="")

    row = col.row(align=True)

    for i in range(24,32):
        row.prop(params, "fk_layers", index=i, toggle=True, text="")


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.0000, 0.0000, 0.3333
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['Bone'] = bone.name

    bone = arm.edit_bones.new('Bone.001')
    bone.head[:] = 0.0000, 0.0000, 0.3333
    bone.tail[:] = 0.0000, 0.0000, 0.6667
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['Bone']]
    bones['Bone.001'] = bone.name

    bone = arm.edit_bones.new('Bone.002')
    bone.head[:] = 0.0000, 0.0000, 0.6667
    bone.tail[:] = 0.0000, 0.0000, 1.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['Bone.001']]
    bones['Bone.002'] = bone.name
    
    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bone']]
    pbone.gamerig.name = 'tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.chain_length = 3
    except AttributeError:
        pass
    try:
        pbone.gamerig.stretchable = True
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['Bone.001']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.002']]
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
