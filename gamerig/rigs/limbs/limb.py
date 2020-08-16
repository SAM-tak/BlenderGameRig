import bpy, itertools
from rna_prop_ui import rna_idprop_ui_prop_get
from math import ( trunc, radians )
from mathutils import ( Vector, Quaternion )
from ...utils import (
    copy_bone, ctrlname, mchname, insert_before_first_period,
    connected_children_names, find_root_bone,
    create_widget,
    MetarigError
)
from ..widgets import create_sphere_widget, create_limb_widget, create_ikarrow_widget, create_directed_circle_widget

class Limb:
    def __init__(self, obj, bone_name, metabone):
        """ Initialize limb rig and key rig properties """
        self.obj       = obj
        self.params    = metabone.gamerig

        self.rot_axis  = self.params.rotation_axis
        self.allow_ik_stretch = self.params.allow_ik_stretch

        # Assign values to FK layers props if opted by user
        if self.params.fk_extra_layers:
            self.fk_layers = list(self.params.fk_layers)
        else:
            self.fk_layers = None
        
        self.root_bone = find_root_bone(obj, bone_name)


    def create_parent( self ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        name = get_bone_name( org_bones[0], 'mch', 'parent' )

        mch = copy_bone( self.obj, org_bones[0], name )
        self.orient_bone( eb[mch], 'y' )
        eb[ mch ].length = eb[ org_bones[0] ].length / 4

        eb[ mch ].parent = eb[ org_bones[0] ].parent

        eb[ mch ].roll = 0.0

        return mch


    def postprocess_parent(self):

        mch = self.bones['parent']

        # Constraints
        if self.root_bone:
            self.make_constraint( mch, {
                'constraint'  : 'COPY_ROTATION',
                'subtarget'   : self.root_bone
            })

            self.make_constraint( mch, {
                'constraint'  : 'COPY_SCALE',
                'subtarget'   : self.root_bone
            })
        else:
            self.make_constraint( mch, {
                'constraint'   : 'LIMIT_ROTATION',
                'use_limit_x'  : True,
                'min_x'        : 0,
                'max_x'        : 0,
                'use_limit_y'  : True,
                'min_y'        : 0,
                'max_y'        : 0,
                'use_limit_z'  : True,
                'min_z'        : 0,
                'max_z'        : 0,
                'target_space' : 'WORLD',
                'owner_space'  : 'WORLD'
            })


    def create_ik( self, parent ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        ctrl = copy_bone(
            self.obj,
            org_bones[0],
            get_bone_name( org_bones[0], 'ctrl', 'ik' )
        )
        mch = copy_bone(
            self.obj,
            org_bones[0],
            get_bone_name( org_bones[0], 'mch',  'ik' )
        )
        mch2 = copy_bone(
            self.obj,
            org_bones[1],
            get_bone_name( org_bones[1], 'mch',  'ik' )
        )
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

        # Parenting
        eb[ ctrl    ].parent = eb[ parent ]
        eb[ mch_str ].parent = eb[ parent ]
        eb[ mch     ].parent = eb[ parent ]
        eb[ mch2    ].parent = eb[ mch ]
        
        return {
            'ctrl'          : { 'limb' : ctrl },
            'mch'           : [ mch, mch2 ],
            'mch_target'    : mch_target,
            'mch_str'       : mch_str
        }


    def postprocess_ik( self ):
        ctrl = self.bones['ik']['ctrl']['limb']
        mch_str = self.bones['ik']['mch_str']
        mch = self.bones['ik']['mch']
        mch_target = self.bones['ik']['mch_target']

        self.make_constraint( mch[1], {
            'constraint'  : 'IK',
            'subtarget'   : mch_target,
            'chain_count' : 2,
            'use_stretch' : self.allow_ik_stretch,
        })

        pb = self.obj.pose.bones
        pb[ mch[0] ].ik_stretch = 0.1
        pb[ mch[1] ].ik_stretch = 0.1

        # IK constraint Rotation locks
        for axis in ['x','y','z']:
            if axis != self.rot_axis:
               setattr( pb[ mch[1] ], 'lock_ik_' + axis, True )
        if self.rot_axis == 'automatic':
            pb[ mch[1] ].lock_ik_x = False
        else:
            pb[ ctrl ].rotation_quaternion = Quaternion(
                (1.0 if self.rot_axis == 'x' else 0.0, 1.0 if self.rot_axis == 'y' else 0.0, 1.0 if self.rot_axis == 'z' else 0.0),
                radians(-90.0)
            )

        # Locks and Widget
        pb[ ctrl ].lock_location = True, True, True
        pb[ ctrl ].lock_rotation = False, False, False
        pb[ ctrl ].lock_rotation_w = False
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
        mch = self.bones['fk']['mch']

        # Constrain MCH's scale to root
        if self.root_bone:
            self.make_constraint( mch, {
                'constraint'  : 'COPY_SCALE',
                'subtarget'   : self.root_bone
            })

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

        # Limb Follow Driver
        pb[fk[0]]['FK Limb Follow'] = 0.0
        prop = rna_idprop_ui_prop_get( pb[fk[0]], 'FK Limb Follow', create = True )

        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'FK Limb Follow'

        drv = pb[ parent ].constraints[ 0 ].driver_add("influence").driver

        drv.type = 'AVERAGE'
        var = drv.variables.new()
        var.name = 'fk_limb_follow'
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[fk[0]].path_from_id() + '[' + '"' + prop.name + '"' + ']'

        # Create IK/FK switch property
        pb[fk[0]]['IK/FK']  = 0.0
        prop = rna_idprop_ui_prop_get( pb[fk[0]], 'IK/FK', create=True )
        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'IK/FK Switch'

        # Constrain IK first mch to controller bone
        self.make_constraint(ik['mch'][0], {
            'constraint'  : 'COPY_TRANSFORMS',
            'subtarget'   : ik['ctrl']['limb']
        })

        # Constrain org to IK and FK bones
        ik =  [ i for i in ik['mch'] ] + [ ik['mch_target'] ]

        for o, i, f in itertools.zip_longest( org, ik, fk ):
            if i is not None:
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
            var.targets[0].data_path = pb[fk[0]].path_from_id() + '['+ '"' + prop.name + '"' + ']'

            self.make_constraint(o, {
                'constraint'  : 'MAINTAIN_VOLUME'
            })


    def generate(self, create_terminal, script_template):
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in self.org_bones[1:]:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        bones = {}

        # Create mch limb parent
        bones['parent'] = self.create_parent()
        bones['fk']     = self.create_fk(bones['parent'])
        bones['ik']     = self.create_ik(bones['parent'])

        self.org_parenting(self.org_bones)

        self.bones = create_terminal( bones )

        return self.create_script( bones, script_template )


    def postprocess(self):
        self.postprocess_parent()
        self.postprocess_fk()
        self.postprocess_ik()
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

        constraint['target'] = self.obj

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            if p in dir( const ):
                setattr( const, p, constraint[p] )
            else:
                raise MetarigError(
                    "GAMERIG ERROR: property %s does not exist in %s constraint" % (
                        p, constraint['constraint']
                ))


    def setup_ik_stretch(self, bones, pb, pb_master):
        if self.allow_ik_stretch:
            self.make_constraint(bones['ik']['mch_str'], {
                'constraint'  : 'LIMIT_SCALE',
                'use_min_y'   : True,
                'use_max_y'   : True,
                'max_y'       : 1.05,
                'owner_space' : 'LOCAL'
            })
            
            # Create ik stretch property
            pb_master['IK Stretch'] = 1.0
            prop = rna_idprop_ui_prop_get( pb_master, 'IK Stretch', create=True )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'IK Stretch'

            # Add driver to limit scale constraint influence
            b        = bones['ik']['mch_str']
            drv      = pb[b].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'ik_stretch'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '['+ '"' + prop.name + '"' + ']'

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
            prop = rna_idprop_ui_prop_get( pb_master, 'IK Follow', create=True )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'IK Follow'

            drv      = pb[mch_ik_socket].constraints[-1].driver_add("influence").driver
            drv.type = 'SUM'

            var = drv.variables.new()
            var.name = 'ik_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_master.path_from_id() + '['+ '"' + prop.name + '"' + ']'


    def create_script(self, bones, script_template):
        # All ctrls have IK/FK switch
        controls =  [ bones['ik']['ctrl']['limb'] ]
        controls += bones['fk']['ctrl']
        controls += bones['ik']['ctrl']['terminal']

        controls_string = ", ".join(["'" + x + "'" for x in controls])

        # IK ctrl has IK stretch
        ik_ctrl = [
            bones['ik']['mch'][0],
            bones['ik']['mch'][1],
            bones['ik']['mch_target']
        ]

        ik_ctrl_string = ", ".join(["'" + x + "'" for x in ik_ctrl])

        code = script_template % (
            controls_string,
            ik_ctrl_string,
            bones['fk']['ctrl'][0],
            bones['fk']['ctrl'][0]
        )

        if self.allow_ik_stretch or self.root_bone:
            code += """
if is_selected( ik_ctrl ):
"""
            if self.allow_ik_stretch:
                code += """
    # IK Stretch on IK Control bone
    layout.prop( pose_bones[ parent ], '["IK Stretch"]', text = 'IK Stretch (%s)', slider = True )
""" % bones['fk']['ctrl'][0]
            if self.root_bone:
                code += """
    # IK Follow on IK Control bone
    layout.prop( pose_bones[ parent ], '["IK Follow"]', text = 'IK Follow (%s)', slider = True )
""" % bones['fk']['ctrl'][0]
        return code


    @staticmethod
    def add_parameters( params ):
        """ Add the parameters of this rig type to the
            RigParameters PropertyGroup
        """
        params.rotation_axis = bpy.props.EnumProperty(
            items   = [
                ('x', 'X', 'X Positive Direction'),
                ('y', 'Y', 'Y Positive Direction'),
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

    @staticmethod
    def operator_script(subclass, rig_id):
        return '''
class {subclass}_SnapIKRootController(bpy.types.Operator):
    """ Snaps IK Root Controller position to proper position.
    """
    bl_idname = "gamerig.{_subclass}_snap_ikroot_{rig_id}"
    bl_label = "Snap IK Root Controller to proper position"
    bl_description = "Snap IK Root Controller to current IKed position (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    ik : bpy.props.StringProperty(name="IK controller")
    mch : bpy.props.StringProperty(name="IKed Bone")

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

            ctrl  = obj.pose.bones[self.ik]
            mch = obj.pose.bones[self.mch]

            # Thigh position
            match_pose_translation(ctrl, mch)
            match_pose_rotation(ctrl, mch)
            match_pose_scale(ctrl, mch)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}

classes.append({subclass}_SnapIKRootController)


'''.format(subclass=subclass, _subclass=subclass.lower(), rig_id=rig_id)


def get_bone_name( name, btype, suffix = '' ):
    if suffix:
        name = insert_before_first_period(name, '_' + suffix)
    
    if btype == 'mch':
        name = mchname( name )
    elif btype == 'ctrl':
        name = ctrlname( name )

    return name
