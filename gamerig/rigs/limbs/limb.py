import bpy, itertools
from rna_prop_ui import rna_idprop_ui_create
from math import radians
from mathutils import Vector, Quaternion
from ...utils import copy_bone, ctrlname, mchname, insert_before_first_period, find_root_bone, MetarigError
from ..widgets import create_limb_widget, create_ikarrow_widget, create_ikdir_widget, create_directed_circle_widget


class Limb:
    def __init__(self, obj, bone_name, metabone):
        """ Initialize limb rig and key rig properties """
        self.obj       = obj
        self.params    = metabone.gamerig

        self.rot_axis  = self.params.rotation_axis
        self.allow_ik_stretch = self.params.allow_ik_stretch
        self.root_vector_ik = self.params.support_ik_mode == 'root' or self.params.support_ik_mode == 'both'
        self.pole_vector_ik = self.params.support_ik_mode == 'pole' or self.params.support_ik_mode == 'both'

        # Assign values to FK layers props if opted by user
        if self.params.fk_extra_layers:
            self.fk_layers = list(self.params.fk_layers)
        else:
            self.fk_layers = None
        
        self.root_bone = find_root_bone(obj, bone_name)
        self.virtual_root_bone = self.root_bone
        if not self.virtual_root_bone:
            virtual_root_bone_name = get_bone_name('virtual', 'mch', 'root')
            if virtual_root_bone_name in self.obj.data.edit_bones:
                self.virtual_root_bone = virtual_root_bone_name
            else:
                self.virtual_root_bone = virtual_root_bone_name
                virtual_root_bone = obj.data.edit_bones.new(virtual_root_bone_name)
                virtual_root_bone.length = 0.5


    def create_parent( self ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        mch = copy_bone( self.obj, org_bones[0], get_bone_name( org_bones[0], 'mch', 'parent' ) )
        
        eb[ mch ].tail[:] = eb[ mch ].head + eb[ self.virtual_root_bone ].vector
        eb[ mch ].length = eb[ org_bones[0] ].length / 4
        eb[ mch ].parent = eb[ org_bones[0] ].parent
        eb[ mch ].roll = eb[ self.virtual_root_bone ].roll

        return mch


    def postprocess_parent(self):

        mch = self.bones['parent']

        # Constraints
        self.make_constraint( mch, {
            'constraint'  : 'COPY_ROTATION',
            'subtarget'   : self.virtual_root_bone
        })

        self.make_constraint( mch, {
            'constraint'  : 'COPY_SCALE',
            'subtarget'   : self.virtual_root_bone
        })


    def create_ik( self, parent, needs_controller_parent ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        ctrl = None
        mch = None
        mch_nostr_1 = None
        mch_nostr_2 = None
        mch_pole_1 = None
        mch_pole_2 = None
        mch_pole_nostr_1 = None
        mch_pole_nostr_2 = None
        mch_final_1 = None
        mch_final_2 = None
        if self.root_vector_ik:
            ctrl = copy_bone(
                self.obj,
                org_bones[0],
                get_bone_name( org_bones[0], 'ctrl',  'ik' )
            )
            mch = copy_bone(
                self.obj,
                org_bones[1],
                get_bone_name( org_bones[1], 'mch',  'ik' )
            )
            if self.allow_ik_stretch:
                mch_nostr_1 = copy_bone(
                    self.obj,
                    org_bones[0],
                    get_bone_name( org_bones[1], 'mch',  'ik1_nostr' )
                )
                mch_nostr_2 = copy_bone(
                    self.obj,
                    org_bones[1],
                    get_bone_name( org_bones[1], 'mch',  'ik2_nostr' )
                )
        if self.pole_vector_ik:
            mch_pole_1 = copy_bone(
                self.obj,
                org_bones[0],
                get_bone_name( org_bones[0], 'mch',  'ik_pole1' )
            )
            mch_pole_2 = copy_bone(
                self.obj,
                org_bones[1],
                get_bone_name( org_bones[1], 'mch',  'ik_pole2' )
            )
            if self.allow_ik_stretch:
                mch_pole_nostr_1 = copy_bone(
                    self.obj,
                    org_bones[0],
                    get_bone_name( org_bones[0], 'mch',  'ik_pole1_nostr' )
                )
                mch_pole_nostr_2 = copy_bone(
                    self.obj,
                    org_bones[1],
                    get_bone_name( org_bones[1], 'mch',  'ik_pole2_nostr' )
                )

        if self.allow_ik_stretch or self.root_vector_ik and self.pole_vector_ik:
            mch_final_1 = copy_bone(
                self.obj,
                org_bones[0],
                get_bone_name(org_bones[0], 'mch',  'ik_final')
            )
            mch_final_2 = copy_bone(
                self.obj,
                org_bones[1],
                get_bone_name(org_bones[1], 'mch',  'ik_final')
            )
        else:
            mch_final_1 = ctrl if ctrl else mch_pole_1
            mch_final_2 = mch if mch else mch_pole_2

        mch_target = copy_bone(
            self.obj,
            org_bones[2],
            get_bone_name( org_bones[2], 'mch',  'ik_target' )
        )
        eb[ mch_target ].length /= 4

        # Create MCH Stretch
        mch_str = copy_bone(
            self.obj,
            org_bones[0],
            get_bone_name( org_bones[0], 'mch', 'ik_stretch' )
        )

        eb[ mch_str ].tail = eb[ org_bones[2] ].head

        dir_ctrl = None
        mch_pole_target = None
        if self.pole_vector_ik:
            # Create IK Direction Controller
            dir_ctrl = copy_bone(
                self.obj,
                mch_str,
                get_bone_name( org_bones[0], 'ctrl', 'ik_direction' )
            )

            eb[ dir_ctrl ].head = eb[ mch_str ].head + (eb[ mch_str ].tail - eb[ mch_str ].head) / 2
            eb[ dir_ctrl ].tail = eb[ dir_ctrl ].head + ( -eb[ dir_ctrl ].z_axis if self.rot_axis == 'x' else eb[ dir_ctrl ].x_axis ) * eb[ dir_ctrl ].length
            eb[ dir_ctrl ].align_roll(eb[ mch_str ].y_axis)
            eb[ dir_ctrl ].inherit_scale = 'NONE'

            mch_pole_target = copy_bone(
                self.obj,
                org_bones[0],
                get_bone_name( org_bones[0], 'mch', 'ik_pole_target' )
            )
            eb[ mch_pole_target ].tail = eb[ dir_ctrl ].head + ( eb[ dir_ctrl ].x_axis if self.rot_axis == 'x' else eb[ dir_ctrl ].z_axis ) * eb[ dir_ctrl ].length * 1.1
            eb[ mch_pole_target ].head = eb[ dir_ctrl ].head + ( eb[ dir_ctrl ].x_axis if self.rot_axis == 'x' else eb[ dir_ctrl ].z_axis ) * eb[ dir_ctrl ].length


        # Parenting
        eb[mch_str].parent = eb[parent]
        if self.root_vector_ik:
            eb[ctrl].parent = eb[parent]
            eb[mch].parent = eb[ctrl]
            if self.allow_ik_stretch:
                eb[mch_nostr_1].parent = eb[parent]
                eb[mch_nostr_2].parent = eb[mch_nostr_1]
        if self.pole_vector_ik:
            eb[mch_pole_1].parent = eb[parent]
            eb[mch_pole_2].parent = eb[mch_pole_1]
            if self.allow_ik_stretch:
                eb[mch_pole_nostr_1].parent = eb[parent]
                eb[mch_pole_nostr_2].parent = eb[mch_pole_nostr_1]
        if self.allow_ik_stretch or self.root_vector_ik and self.pole_vector_ik:
            eb[mch_final_1].parent = eb[parent]
            eb[mch_final_2].parent = eb[mch_final_1]

        if needs_controller_parent:
            # Parenting
            if self.pole_vector_ik:
                mch_ctrl_parent = copy_bone(
                    self.obj,
                    dir_ctrl,
                    get_bone_name( org_bones[0], 'mch', 'ik_ctrl_parent' )
                )
                eb[ mch_ctrl_parent ].length /= 6
                eb[ mch_ctrl_parent ].inherit_scale = 'NONE'

                mch_ctrl_parent_target = copy_bone(
                    self.obj,
                    mch_target,
                    get_bone_name( org_bones[0], 'mch', 'ik_ctrl_parent_target' )
                )

                eb[mch_ctrl_parent].parent = eb[mch_str]
                eb[dir_ctrl].parent = eb[mch_ctrl_parent]
                eb[mch_pole_target].parent = eb[dir_ctrl]

            return {
                'ctrl'                   : { 'limb' : [ctrl, dir_ctrl], 'additional' : [] },
                'mch'                    : mch,
                'mch_nostr'              : [mch_nostr_1, mch_nostr_2],
                'mch_pole'               : [mch_pole_1, mch_pole_2],
                'mch_pole_nostr'         : [mch_pole_nostr_1, mch_pole_nostr_2],
                'mch_final'              : [mch_final_1, mch_final_2],
                'mch_target'             : mch_target,
                'mch_str'                : mch_str,
                'mch_pole_target'        : mch_pole_target,
                'mch_ctrl_parent'        : mch_ctrl_parent,
                'mch_ctrl_parent_target' : mch_ctrl_parent_target
            }

        else:

            # Parenting
            if self.pole_vector_ik:
                eb[dir_ctrl].parent = eb[mch_str]
                eb[mch_pole_target].parent = eb[dir_ctrl]

            return {
                'ctrl'            : { 'limb' : [ctrl, dir_ctrl], 'additional' : [] },
                'mch'             : mch,
                'mch_nostr'       : [mch_nostr_1, mch_nostr_2],
                'mch_pole'        : [mch_pole_1, mch_pole_2],
                'mch_pole_nostr'  : [mch_pole_nostr_1, mch_pole_nostr_2],
                'mch_final'       : [mch_final_1, mch_final_2],
                'mch_target'      : mch_target,
                'mch_str'         : mch_str,
                'mch_pole_target' : mch_pole_target
            }


    def postprocess_ik( self, reverse_ik_widget ):
        ctrl = self.bones['ik']['ctrl']['limb'][0]
        dir_ctrl = self.bones['ik']['ctrl']['limb'][1]
        mch = self.bones['ik']['mch']
        mch_nostr = self.bones['ik']['mch_nostr']
        mch_pole = self.bones['ik']['mch_pole']
        mch_pole_nostr = self.bones['ik']['mch_pole_nostr']
        mch_target = self.bones['ik']['mch_target']
        mch_pole_target = self.bones['ik']['mch_pole_target']

        if self.root_vector_ik:
            self.make_constraint( mch, {
                'constraint'        : 'IK',
                'subtarget'         : mch_target,
                'chain_count'       : 2,
                'use_stretch'       : self.allow_ik_stretch
            })
            if self.allow_ik_stretch:
                self.make_constraint( mch_nostr[0], {
                    'constraint'    : 'COPY_TRANSFORMS',
                    'subtarget'     : ctrl
                })
                self.make_constraint( mch_nostr[1], {
                    'constraint'    : 'IK',
                    'subtarget'     : mch_target,
                    'chain_count'   : 2,
                    'use_stretch'   : False
                })
        if self.pole_vector_ik:
            self.make_constraint( mch_pole[1], {
                'constraint'        : 'IK',
                'subtarget'         : mch_target,
                'chain_count'       : 2,
                'use_stretch'       : self.allow_ik_stretch,
                'pole_target'       : self.obj,
                'pole_subtarget'    : mch_pole_target
            })
            if self.allow_ik_stretch:
                self.make_constraint( mch_pole_nostr[1], {
                    'constraint'    : 'IK',
                    'subtarget'     : mch_target,
                    'chain_count'   : 2,
                    'use_stretch'   : False,
                    'pole_target'   : self.obj,
                    'pole_subtarget': mch_pole_target
                })

        pb = self.obj.pose.bones
        if ctrl:
            pb[ ctrl ].ik_stretch = 0.1
        if mch:
            pb[ mch ].ik_stretch = 0.1
        for i in mch_nostr:
            if i:
                pb[i].ik_stretch = 0.1
        for i in mch_pole:
            if i:
                pb[i].ik_stretch = 0.1
        for i in mch_pole_nostr:
            if i:
                pb[i].ik_stretch = 0.1

        # IK constraint Rotation locks
        if mch:
            for axis in ['x','y','z']:
                if axis != self.rot_axis:
                    setattr( pb[ mch ], 'lock_ik_' + axis, True )
            if self.rot_axis == 'automatic':
                pb[ mch ].lock_ik_x = False

        # Locks and Widget
        if dir_ctrl:
            pb[ dir_ctrl ].lock_location = True, True, True
            pb[ dir_ctrl ].lock_rotation = self.rot_axis == 'x', True, self.rot_axis != 'x'
            pb[ dir_ctrl ].rotation_mode = 'XYZ' if self.rot_axis == 'x' else 'ZYX'
            pb[ dir_ctrl ].lock_scale = True, True, True

            create_ikdir_widget( self.obj, dir_ctrl, -1.0 if reverse_ik_widget else 1.0 )

        if ctrl:
            pb[ ctrl ].lock_scale = True, True, True

            create_ikarrow_widget( self.obj, ctrl )


    def create_fk( self, parent ):
        org_bones = self.org_bones.copy()

        eb = self.obj.data.edit_bones

        ctrls = []

        for o in org_bones:
            bone = copy_bone( self.obj, o, get_bone_name( o, 'ctrl', 'fk' ) )
            ctrls.append( bone )

        # MCH
        mch = copy_bone(self.obj, org_bones[-1], get_bone_name( o, 'mch', 'fk' ))

        eb[ mch ].length /= 4
        
        # Parenting
        if len(ctrls) < 4:
            if len(ctrls) < 3:
                raise MetarigError("gamerig.limb: rig '%s' have no enough length " % parent)

            eb[ ctrls[0] ].parent      = eb[ parent   ]
            eb[ ctrls[1] ].parent      = eb[ ctrls[0] ]
            eb[ ctrls[1] ].use_connect = True
            eb[ ctrls[2] ].parent      = eb[ mch      ]
            eb[ mch      ].parent      = eb[ ctrls[1] ]
            eb[ mch      ].use_connect = True
        else:
            eb[ ctrls[0] ].parent      = eb[ parent   ]
            eb[ ctrls[1] ].parent      = eb[ ctrls[0] ]
            eb[ ctrls[1] ].use_connect = True
            eb[ ctrls[2] ].parent      = eb[ ctrls[1] ]
            eb[ ctrls[2] ].use_connect = True
            eb[ ctrls[3] ].parent      = eb[ mch      ]
            eb[ mch      ].parent      = eb[ ctrls[2] ]
            eb[ mch      ].use_connect = True

        return { 'ctrl' : ctrls, 'mch' : mch }


    def postprocess_fk(self):
        ctrls = self.bones['fk']['ctrl']

        # Locks and widgets
        pb = self.obj.pose.bones
        pb[ ctrls[2] ].lock_location = True, True, True
        pb[ ctrls[2] ].lock_scale = True, True, True

        create_limb_widget(self.obj, ctrls[0])
        create_limb_widget(self.obj, ctrls[1])

        if len(ctrls) < 4:
            create_directed_circle_widget(self.obj, ctrls[2], radius=-0.4, head_tail=0.0) # negative radius is reasonable. to flip xz
        else:
            create_limb_widget(self.obj, ctrls[2])
            create_directed_circle_widget(self.obj, ctrls[3], radius=-0.4, head_tail=0.5) # negative radius is reasonable. to flip xz
        
        for c in ctrls:
            if self.fk_layers:
                pb[c].bone.layers = self.fk_layers


    def org_parenting( self, org ):
        eb = self.obj.data.edit_bones
        # re-parent ORGs in a connected chain
        for i,o in enumerate(org):
            if i > 0:
                eb[o].parent = eb[ org[i-1] ]
                if i <= len(org)-1:
                    eb[o].use_connect = True


    def setup_switch( self, org, ik, fk, parent ):
        pb = self.obj.pose.bones
        pb_master = pb[ik['ctrl']['terminal'][-1]]

        # Toggle Pole Driver
        if self.root_vector_ik and self.pole_vector_ik:
            pb_master['IK Pole Mode'] = 0
            rna_idprop_ui_create( pb_master, 'IK Pole Mode', default=0.0, description='IK solver using Pole Target', overridable=True )

            drv = pb[ ik['ctrl']['limb'][0] ].bone.driver_add("hide").driver
            drv.type = 'AVERAGE'
            var = drv.variables.new()
            var.name = 'ik_pole_mode'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'

            fcu = pb[ ik['ctrl']['limb'][1] ].bone.driver_add("hide")
            drv = fcu.driver
            drv.type = 'AVERAGE'
            var = drv.variables.new()
            var.name = 'ik_pole_mode'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'

            drv_modifier = fcu.modifiers.new('GENERATOR')
            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

        # Limb Follow Driver
        pb[fk[0]]['FK Limb Follow'] = 0.0
        rna_idprop_ui_create( pb[fk[0]], 'FK Limb Follow', default=0.0, description='FK Limb Follow', overridable=True )

        drv = pb[ parent ].constraints[ 0 ].driver_add("influence").driver

        drv.type = 'AVERAGE'
        var = drv.variables.new()
        var.name = 'fk_limb_follow'
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[fk[0]].path_from_id() + '["FK Limb Follow"]'

        # Create IK/FK switch property
        pb[fk[0]]['IK/FK']  = 0.0
        rna_idprop_ui_create( pb[fk[0]], 'IK/FK', default=0.0, description='IK/FK Switch', overridable=True )

        # Constrain IK to IK final bones
        if self.allow_ik_stretch or self.root_vector_ik and self.pole_vector_ik:
            for f, s1, s1n, s2, s2n in itertools.zip_longest(ik['mch_final'], [ik['ctrl']['limb'][0], ik['mch']], ik['mch_nostr'], ik['mch_pole'], ik['mch_pole_nostr']):
                if s1:
                    self.make_constraint(f, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : s1
                    })

                if s1n:
                    self.make_constraint(f, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : s1n
                    })

                    drv = pb[f].constraints[-1].driver_add("influence").driver
                    drv.type = 'SCRIPTED'
                    drv.expression = '1.0 - ik_stretch'

                    var = drv.variables.new()
                    var.name = 'ik_stretch'
                    var.type = "SINGLE_PROP"
                    var.targets[0].id = self.obj
                    var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'
                    
                if s2:
                    self.make_constraint(f, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : s2
                    })

                    if self.root_vector_ik:
                        drv = pb[f].constraints[-1].driver_add("influence").driver
                        drv.type = 'AVERAGE'

                        var = drv.variables.new()
                        var.name = 'ik_pole_mode'
                        var.type = "SINGLE_PROP"
                        var.targets[0].id = self.obj
                        var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'

                if s2n:
                    self.make_constraint(f, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : s2n
                    })

                    if self.root_vector_ik:
                        drv = pb[f].constraints[-1].driver_add("influence").driver
                        drv.type = 'SCRIPTED'
                        drv.expression = '(1.0 - ik_stretch) * ik_pole_mode'

                        var = drv.variables.new()
                        var.name = 'ik_stretch'
                        var.type = "SINGLE_PROP"
                        var.targets[0].id = self.obj
                        var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'
                        var = drv.variables.new()
                        var.name = 'ik_pole_mode'
                        var.type = "SINGLE_PROP"
                        var.targets[0].id = self.obj
                        var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'
                    else:
                        drv = pb[f].constraints[-1].driver_add("influence").driver
                        drv.type = 'AVERAGE'

                        var = drv.variables.new()
                        var.name = 'ik_pole_mode'
                        var.type = "SINGLE_PROP"
                        var.targets[0].id = self.obj
                        var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'

        if self.allow_ik_stretch or self.root_vector_ik and self.pole_vector_ik:
            first = (ik['mch_final'][0])
            second = (ik['mch_final'][1])
        else:
            first = (ik['ctrl']['limb'][0], ik['mch_nostr'][0], ik['mch_pole'][0], ik['mch_pole_nostr'][0])
            second = (ik['mch'], ik['mch_nostr'][1], ik['mch_pole'][1], ik['mch_pole_nostr'][1])

        # Constrain org to IK and FK bones
        for o, i, f in itertools.zip_longest(org, [first, second, ik['mch_target']], fk):
            if i is not None:
                if isinstance(i, tuple):
                    for j in i:
                        if j is not None:
                            self.make_constraint(o, {
                                'constraint'  : 'COPY_TRANSFORMS',
                                'subtarget'   : j
                            })

                            # Add driver to relevant constraint
                            if self.allow_ik_stretch and j in ik['mch_nostr']:
                                drv = pb[o].constraints[-1].driver_add("influence").driver
                                drv.type = 'SCRIPTED'
                                drv.expression = '1.0 - ik_stretch'

                                var = drv.variables.new()
                                var.name = 'ik_stretch'
                                var.type = "SINGLE_PROP"
                                var.targets[0].id = self.obj
                                var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'
                            
                            if self.root_vector_ik and self.pole_vector_ik:
                                if j in ik['mch_pole']:
                                    drv = pb[o].constraints[-1].driver_add("influence").driver
                                    drv.type = 'AVERAGE'

                                    var = drv.variables.new()
                                    var.name = 'ik_pole_mode'
                                    var.type = "SINGLE_PROP"
                                    var.targets[0].id = self.obj
                                    var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'

                                if self.allow_ik_stretch and j in ik['mch_pole_nostr']:
                                    drv = pb[o].constraints[-1].driver_add("influence").driver
                                    drv.type = 'SCRIPTED'
                                    drv.expression = '(1.0 - ik_stretch) * ik_pole_mode'

                                    var = drv.variables.new()
                                    var.name = 'ik_stretch'
                                    var.type = "SINGLE_PROP"
                                    var.targets[0].id = self.obj
                                    var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'
                                    var = drv.variables.new()
                                    var.name = 'ik_pole_mode'
                                    var.type = "SINGLE_PROP"
                                    var.targets[0].id = self.obj
                                    var.targets[0].data_path = pb_master.path_from_id() + '["IK Pole Mode"]'
                                
                            elif self.allow_ik_stretch and j in ik['mch_pole_nostr']:
                                drv = pb[o].constraints[-1].driver_add("influence").driver
                                drv.type = 'SCRIPTED'
                                drv.expression = '1.0 - ik_stretch'

                                var = drv.variables.new()
                                var.name = 'ik_stretch'
                                var.type = "SINGLE_PROP"
                                var.targets[0].id = self.obj
                                var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'
                else:
                    self.make_constraint(o, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : i
                    })
            self.make_constraint(o, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : f
            })

            # Add driver to relevant constraint
            drv = pb[o].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_fk_switch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[fk[0]].path_from_id() + '["IK/FK"]'

            self.make_constraint(o, {
                'constraint'  : 'MAINTAIN_VOLUME'
            })


    def generate(self, create_terminal, script_template, needs_ik_controller_parent = False):
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in self.org_bones[1:]:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        bones = {}

        # Create mch limb parent
        bones['parent'] = self.create_parent()
        bones['fk']     = self.create_fk(bones['parent'])
        bones['ik']     = self.create_ik(bones['parent'], needs_ik_controller_parent)

        self.org_parenting(self.org_bones)

        self.bones = create_terminal( bones )

        return self.create_script( bones, script_template )


    def postprocess(self, reverse_ik_widget = False):
        self.postprocess_parent()
        self.postprocess_fk()
        self.postprocess_ik(reverse_ik_widget)
        bones = self.bones
        self.setup_switch(self.org_bones, bones['ik'], bones['fk']['ctrl'], bones['parent'])


    def orient_bone( self, eb, axis, scale = 1.0, reverse = False ):
        v = Vector((0,0,0))

        setattr(v, axis, scale)

        if reverse:
            tail_vec = v @ self.obj.matrix_world
            eb.head[:] = eb.tail
            eb.tail[:] = eb.head + tail_vec
        else:
            tail_vec = v @ self.obj.matrix_world
            eb.tail[:] = eb.head + tail_vec

        eb.roll = 0.0


    def make_constraint( self, bone, constraint ):
        pb = self.obj.pose.bones

        owner_pb = pb[bone]
        const    = owner_pb.constraints.new( constraint['constraint'] )

        if 'target' in dir(const):
            if 'target' in constraint:
                const.target = constraint['target']
            else:
                const.target = self.obj
        if 'subtarget' in dir(const):
            if 'subtarget' in constraint:
                const.subtarget = constraint['subtarget']

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            if p in dir( const ):
                if p != 'target' and p != 'subtarget':
                    setattr( const, p, constraint[p] )
            else:
                raise MetarigError(f"GAMERIG ERROR: property '{p}' does not exist in {constraint['constraint']} constraint")


    def setup_ik_stretch(self, bones, pb, pb_master):
        if self.allow_ik_stretch:
            self.make_constraint(bones['ik']['mch_str'], {
                'constraint'  : 'LIMIT_SCALE',
                'use_min_y'   : True,
                'use_max_y'   : True,
                'max_y'       : 1.0,
                'owner_space' : 'LOCAL'
            })
            
            # Create ik stretch property
            pb_master['IK Stretch'] = 1.0
            rna_idprop_ui_create( pb_master, 'IK Stretch', default=1.0, description='IK Stretch', overridable=True )

            # Add driver to limit scale constraint influence
            b        = bones['ik']['mch_str']
            drv      = pb[b].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_stretch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '["IK Stretch"]'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0


    def make_ik_follow_bone(self, eb, ctrl):
        """ add IK Follow feature
        """
        if self.root_bone:
            mch_ik_socket = copy_bone( self.obj, self.root_bone, mchname('socket_' + ctrl) )
            eb[ mch_ik_socket ].length /= 4
            eb[ mch_ik_socket ].use_connect = False
            eb[ mch_ik_socket ].parent = None
            eb[ ctrl    ].parent = eb[ mch_ik_socket ]
            return mch_ik_socket


    def setup_ik_follow(self, pb, pb_master, mch_ik_socket):
        """ Add IK Follow constrain and property and driver
        """
        if self.root_bone:
            self.make_constraint(mch_ik_socket, {
                'constraint'   : 'COPY_TRANSFORMS',
                'subtarget'    : self.root_bone,
                'target_space' : 'WORLD',
                'owner_space'  : 'WORLD',
            })

            pb_master['IK Follow'] = 1.0
            rna_idprop_ui_create( pb_master, 'IK Follow', default=1.0, description='IK Follow', overridable=True )

            drv      = pb[mch_ik_socket].constraints[-1].driver_add("influence").driver
            drv.type = 'SUM'

            var = drv.variables.new()
            var.name = 'ik_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '["IK Follow"]'


    def create_script(self, bones, script_template):
        # All ctrls have IK/FK switch
        controls = bones['ik']['ctrl']['limb'] + bones['fk']['ctrl'] + bones['ik']['ctrl']['terminal'] + bones['ik']['ctrl']['additional']

        # IK ctrls has IK stretch
        ik_ctrls = bones['ik']['ctrl']['limb'] + bones['ik']['ctrl']['terminal'] + bones['ik']['ctrl']['additional']

        # non controller ik staff
        ik_mchs = [bones['ik']['mch'], bones['ik']['mch_target']]

        ik_master = bones['ik']['ctrl']['terminal'][-1]

        code = f"""
controls = [{", ".join(["'" + x + "'" if x else "''" for x in controls])}]
ik_ctrls = [{", ".join(["'" + x + "'" if x else "''" for x in ik_ctrls])}]
fk_ctrls = [{", ".join(["'" + x + "'" for x in bones['fk']['ctrl']])}]
ik_mchs  = [{", ".join(["'" + x + "'" if x else "''" for x in ik_mchs])}]
ik_final = [{", ".join(["'" + x + "'" if x else "''" for x in bones['ik']['mch_final']])}]

if is_selected( controls ):
    layout.prop( pose_bones[ '{bones['fk']['ctrl'][0]}' ], '["IK/FK"]', text='IK/FK ({self.org_bones[0]})', slider = True )

"""
        if self.allow_ik_stretch or self.root_bone or (self.root_vector_ik and self.pole_vector_ik):
            code += """
if is_selected( ik_ctrls ):
"""
            if self.allow_ik_stretch:
                code += f"""
    # IK Stretch on IK Control bone
    layout.prop( pose_bones[ '{ik_master}' ], '["IK Stretch"]', text = 'IK Stretch ({self.org_bones[0]})', slider = True )

"""
            if self.root_bone:
                code += f"""
    # IK Follow on IK Control bone
    layout.prop( pose_bones[ '{ik_master}' ], '["IK Follow"]', text = 'IK Follow ({self.org_bones[0]})', slider = True )

"""
            if self.root_vector_ik and self.pole_vector_ik:
                code += f"""
    # IK Pole Mode
    layout.prop( pose_bones[ '{ik_master}' ], '["IK Pole Mode"]', text = 'IK Pole Mode ({self.org_bones[0]})', slider = True )

"""
        code += f"""
if is_selected( fk_ctrls ):
    # FK limb follow
    layout.prop( pose_bones[ '{bones['fk']['ctrl'][0]}' ], '["FK Limb Follow"]', text = 'FK Limb Follow ({self.org_bones[0]})', slider = True)

"""
        return code + script_template


    @staticmethod
    def add_parameters( params ):
        """ Add the parameters of this rig type to the
            RigParameters PropertyGroup
        """
        params.rotation_axis = bpy.props.EnumProperty(
            items   = [
                ('x', 'X', 'X Positive Direction'),
                ('z', 'Z', 'Z Positive Direction')
            ],
            name    = "Rotation Axis",
            default = 'x'
        )

        params.allow_ik_stretch = bpy.props.BoolProperty(
            name        = "Allow IK Stretch",
            default     = True,
            description = "Allow IK Stretch"
        )

        params.support_ik_mode = bpy.props.EnumProperty(
            items   = [
                ('root', 'Root Vector', 'Root Vector'),
                ('pole', 'Pole Vector', 'Pole Vector'),
                ('both', 'Both', 'Both')
            ],
            name    = "Support IK Mode",
            default = 'both'
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


    @staticmethod
    def parameters_ui(layout, params):
        """ Create the ui for the rig parameters."""
        r = layout.row()
        r.prop(params, "rotation_axis")

        r = layout.row()
        r.prop(params, "allow_ik_stretch")

        r = layout.row()
        r.prop(params, "support_ik_mode")

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


def get_bone_name( name, btype, suffix = '' ):
    if suffix:
        name = insert_before_first_period(name, '_' + suffix)
    
    if btype == 'mch':
        name = mchname( name )
    elif btype == 'ctrl':
        name = ctrlname( name )

    return name
