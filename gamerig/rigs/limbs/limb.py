import bpy, re, itertools, math
from rna_prop_ui import rna_idprop_ui_prop_get
from math import trunc
from mathutils import Vector
from ...utils import (
    copy_bone, flip_bone, put_bone, org, basename,
    connected_children_names, find_root_bone,
    create_widget,
    MetarigError
)
from ..widgets import create_sphere_widget, create_limb_widget, create_ikarrow_widget, create_directed_circle_widget
from .arm import create_arm
from .leg import create_leg
from .paw import create_paw
from .ui import create_script
from .limb_utils import *

class Rig:
    def __init__(self, obj, bone_name, params):
        """ Initialize torso rig and key rig properties """
        self.obj       = obj
        self.params    = params

        if params.limb_type == 'arm':
            # The basic limb is the first 3 bones for a arm
            self.org_bones = list([bone_name] + connected_children_names(obj, bone_name))[:3]
        else:
            # The basic limb is the first 4 bones for a paw or leg
            self.org_bones = list([bone_name] + connected_children_names(obj, bone_name))[:4]

        self.limb_type = params.limb_type
        self.rot_axis  = params.rotation_axis
        self.allow_ik_stretch = params.allow_ik_stretch

        # Assign values to FK layers props if opted by user
        if params.fk_extra_layers:
            self.fk_layers = list(params.fk_layers)
        else:
            self.fk_layers = None
        
        self.root_bone = find_root_bone(obj, bone_name)


    def create_parent( self ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        name = get_bone_name( basename( org_bones[0] ), 'mch', 'parent' )

        mch = copy_bone( self.obj, org_bones[0], name )
        orient_bone( self, eb[mch], 'z' )
        eb[ mch ].length = eb[ org_bones[0] ].length / 4

        eb[ mch ].parent = eb[ org_bones[0] ].parent

        eb[ mch ].roll = 0.0

        # Constraints
        if self.root_bone:
            make_constraint( self, mch, {
                'constraint'  : 'COPY_ROTATION',
                'subtarget'   : self.root_bone
            })

            make_constraint( self, mch, {
                'constraint'  : 'COPY_SCALE',
                'subtarget'   : self.root_bone
            })
        else:
            make_constraint( self, mch, {
                'constraint'   : 'LIMIT_ROTATION',
                'use_limit_x'  : True,
                'min_x'        : math.radians(90),
                'max_x'        : math.radians(90),
                'use_limit_y'  : True,
                'min_y'        : 0,
                'max_y'        : 0,
                'use_limit_z'  : True,
                'min_z'        : 0,
                'max_z'        : 0,
                'target_space' : 'LOCAL',
                'owner_space'  : 'WORLD'
            })

        return mch


    def create_ik( self, parent ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        ctrl       = get_bone_name( org_bones[0], 'ctrl', 'ik'        )
        mch_ik     = get_bone_name( org_bones[0], 'mch',  'ik'        )
        mch_target = get_bone_name( org_bones[0], 'mch',  'ik_target' )

        for o, ik in zip( org_bones, [ ctrl, mch_ik, mch_target ] ):
            bone = copy_bone( self.obj, o, ik )

            if org_bones.index(o) == len( org_bones ) - 1:
                eb[ bone ].length /= 4

        # Create MCH Stretch
        mch_str = copy_bone(
            self.obj,
            org_bones[0],
            get_bone_name( org_bones[0], 'mch', 'ik_stretch' )
        )

        if self.limb_type == 'arm':
            eb[ mch_str ].tail = eb[ org_bones[-1] ].head
        else:
            eb[ mch_str ].tail = eb[ org_bones[-2] ].head

        # Parenting
        eb[ ctrl    ].parent = eb[ parent ]
        eb[ mch_str ].parent = eb[ parent ]
        eb[ mch_ik  ].parent = eb[ ctrl   ]
        
        make_constraint( self, mch_ik, {
            'constraint'  : 'IK',
            'subtarget'   : mch_target,
            'chain_count' : 2,
            'use_stretch' : self.allow_ik_stretch,
        })

        pb = self.obj.pose.bones
        pb[ mch_ik ].ik_stretch = 0.1
        pb[ ctrl   ].ik_stretch = 0.1

        # IK constraint Rotation locks
        for axis in ['x','y','z']:
            if axis != self.rot_axis:
               setattr( pb[ mch_ik ], 'lock_ik_' + axis, True )
        if self.rot_axis == 'automatic':
            pb[ mch_ik ].lock_ik_x = False

        # Locks and Widget
        pb[ ctrl ].lock_location = True, True, True
        pb[ ctrl ].lock_rotation = False, False, True
        pb[ ctrl ].lock_scale = True, True, True
        create_ikarrow_widget( self.obj, ctrl )

        return {
            'ctrl'          : { 'limb' : ctrl },
            'mch_ik'        : mch_ik,
            'mch_target'    : mch_target,
            'mch_str'       : mch_str
        }


    def create_fk( self, parent ):
        org_bones = self.org_bones.copy()

        # if self.limb_type == 'paw':  # Paw base chain is one bone longer
        #     org_bones.pop()

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        ctrls = []

        for o in org_bones:
            bone = copy_bone( self.obj, o, get_bone_name( o, 'ctrl', 'fk' ) )
            ctrls.append( bone )

        # MCH
        mch = copy_bone(self.obj, org_bones[-1], get_bone_name( o, 'mch', 'fk' ))

        eb[ mch ].length /= 4
        
        # Parenting
        if self.limb_type == 'arm':
            if len(ctrls) < 3:
                raise MetarigError("gamerig.limb.arm: rig '%s' have no enough length " % parent)

            eb[ ctrls[0] ].parent      = eb[ parent   ]
            eb[ ctrls[1] ].parent      = eb[ ctrls[0] ]
            eb[ ctrls[1] ].use_connect = True
            eb[ ctrls[2] ].parent      = eb[ mch      ]
            eb[ mch      ].parent      = eb[ ctrls[1] ]
            eb[ mch      ].use_connect = True
        else:
            if len(ctrls) < 4:
                raise MetarigError("gamerig.limb: rig '%s' have no enough length " % parent)
            
            eb[ ctrls[0] ].parent      = eb[ parent   ]
            eb[ ctrls[1] ].parent      = eb[ ctrls[0] ]
            eb[ ctrls[1] ].use_connect = True
            eb[ ctrls[2] ].parent      = eb[ ctrls[1] ]
            eb[ ctrls[2] ].use_connect = True
            eb[ ctrls[3] ].parent      = eb[ mch      ]
            eb[ mch      ].parent      = eb[ ctrls[2] ]
            eb[ mch      ].use_connect = True

        if self.root_bone:
            # Constrain MCH's scale to root
            make_constraint( self, mch, {
                'constraint'  : 'COPY_SCALE',
                'subtarget'   : self.root_bone
            })
        else:
            bpy.ops.object.mode_set(mode = 'OBJECT')

        # Locks and widgets
        pb = self.obj.pose.bones
        pb[ ctrls[2] ].lock_location = True, True, True
        pb[ ctrls[2] ].lock_scale = True, True, True

        create_limb_widget(self.obj, ctrls[0])
        create_limb_widget(self.obj, ctrls[1])

        if self.limb_type == 'arm':
            create_directed_circle_widget(self.obj, ctrls[2], radius=-0.4, head_tail=0.0) # negative radius is reasonable. to flip xz
        else:
            create_limb_widget(self.obj, ctrls[2])
            create_directed_circle_widget(self.obj, ctrls[3], radius=-0.4, head_tail=0.5) # negative radius is reasonable. to flip xz
        
        for c in ctrls:
            if self.fk_layers:
                pb[c].bone.layers = self.fk_layers

        return { 'ctrl' : ctrls, 'mch' : mch }


    def org_parenting_and_switch( self, org, ik, fk, parent ):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        # re-parent ORGs in a connected chain
        for i,o in enumerate(org):
            if i > 0:
                eb[o].parent = eb[ org[i-1] ]
                if i <= len(org)-1:
                    eb[o].use_connect = True

        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones

        # Limb Follow Driver
        pb[fk[0]]['fk_limb_follow'] = 0.0
        prop = rna_idprop_ui_prop_get( pb[fk[0]], 'fk_limb_follow', create = True )

        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'FK Limb Follow'

        drv = pb[ parent ].constraints[ 0 ].driver_add("influence").driver

        drv.type = 'AVERAGE'
        var = drv.variables.new()
        var.name = prop.name
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[fk[0]].path_from_id() + '[' + '"' + prop.name + '"' + ']'

        # Create ik/fk switch property
        pb[fk[0]]['ik_fk_rate']  = 0.0
        prop = rna_idprop_ui_prop_get( pb[fk[0]], 'ik_fk_rate', create=True )
        prop["min"]         = 0.0
        prop["max"]         = 1.0
        prop["soft_min"]    = 0.0
        prop["soft_max"]    = 1.0
        prop["description"] = 'IK/FK Switch'

        # Constrain org to IK and FK bones
        iks =  [ ik['ctrl']['limb'] ]
        iks += [ ik[k] for k in [ 'mch_ik', 'mch_target'] ]

        for o, i, f in itertools.zip_longest( org, iks, fk ):
            if i is not None:
                make_constraint( self, o, {
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : i
                })
            make_constraint( self, o, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : f
            })

            # Add driver to relevant constraint
            drv = pb[o].constraints[-1].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = prop.name
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[fk[0]].path_from_id() + '['+ '"' + prop.name + '"' + ']'

            make_constraint( self, o, {
                'constraint'  : 'MAINTAIN_VOLUME'
            })


    def create_terminal( self, limb_type, bones ):
        if   limb_type == 'arm':
            return create_arm( self, bones )
        elif limb_type == 'leg':
            return create_leg( self, bones )
        elif limb_type == 'paw':
            return create_paw( self, bones )


    def generate( self ):
        bpy.ops.object.mode_set(mode ='EDIT')
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

        self.org_parenting_and_switch(self.org_bones, bones['ik'], bones['fk']['ctrl'], bones['parent'])

        bones = self.create_terminal( self.limb_type, bones )

        return [ create_script( bones, self.limb_type, self.allow_ik_stretch, self.root_bone ) ]


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        GameRigParameters PropertyGroup
    """

    items = [
        ('arm', 'Arm', ''),
        ('leg', 'Leg', ''),
        ('paw', 'Paw', '')
    ]
    params.limb_type = bpy.props.EnumProperty(
        items   = items,
        name    = "Limb Type",
        default = 'arm'
    )

    items = [
        ('x', 'X', ''),
        ('y', 'Y', ''),
        ('z', 'Z', '')
    ]
    params.rotation_axis = bpy.props.EnumProperty(
        items   = items,
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
        description = ""
    )

    params.fk_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the FK controls to be on",
        default     = tuple( [ i == 1 for i in range(0, 32) ] )
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""

    r = layout.row()
    r.prop(params, "limb_type")

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


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('upper_arm.L')
    bone.head[:] = -0.0016, 0.0060, -0.0012
    bone.tail[:] = 0.2455, 0.0678, -0.1367
    bone.roll = 2.0724
    bone.use_connect = False
    bones['upper_arm.L'] = bone.name
    bone = arm.edit_bones.new('forearm.L')
    bone.head[:] = 0.2455, 0.0678, -0.1367
    bone.tail[:] = 0.4625, 0.0285, -0.2797
    bone.roll = 2.1535
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_arm.L']]
    bones['forearm.L'] = bone.name
    bone = arm.edit_bones.new('hand.L')
    bone.head[:] = 0.4625, 0.0285, -0.2797
    bone.tail[:] = 0.5265, 0.0205, -0.3273
    bone.roll = 2.2103
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['forearm.L']]
    bones['hand.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['upper_arm.L']]
    pbone.gamerig_type = 'gamerig.limbs.limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig_parameters.allow_ik_stretch = True
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.ik_layers = [
            False, False, False, False, False, False, False, False, True, False,
            False, False, False, False, False, False, False, False, False, False,
            False, False, False, False, False, False, False, False, False, False,
            False, False
        ]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.fk_layers = [
            False, False, False, False, False, False, False, False, True, False,
            False, False, False, False, False, False, False, False, False, False,
            False, False, False, False, False, False, False, False, False, False,
            False, False
        ]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['forearm.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['hand.L']]
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
