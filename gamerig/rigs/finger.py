import bpy
from mathutils import Vector
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    copy_bone, flip_bone, connected_children_names,
    create_circle_widget, create_sphere_widget, create_widget,
    MetarigError,
    basename, mch
)

class Rig:

    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params = params

        if len(self.org_bones) <= 1:
            raise MetarigError("GAMERIG ERROR: Bone '%s': listen bro, that finger rig jusaint put tugetha rite. A little hint, use more than one bone!!" % (basename(bone_name)))


    def generate(self):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Bone name lists
        ctrl_chain    = []
        mch_chain     = []

        # Create ctrl master bone
        org_name  = self.org_bones[0]
        temp_name = basename(org_name)

        suffix = temp_name[-2:]
        master_name      = temp_name[:-5] + "_master" + suffix
        master_name      = copy_bone( self.obj, org_name, master_name )
        ctrl_bone_master = eb[ master_name ]

        ## Parenting bug fix ??
        ctrl_bone_master.use_connect = False
        ctrl_bone_master.parent      = None

        ctrl_bone_master.length = sum(eb[l].length for l in org_bones)

        ## workaround for parenting bug
        root_parent_name = eb[org_name].parent.name

        for bone in org_bones:
            eb[bone].use_connect = False
            eb[bone].parent = None

        # Creating the bone chains
        for name in org_bones:
            # Create control bones
            ctrl_bone = copy_bone( self.obj, name, basename(name) )

            # Create mechanism bones
            mch_bone  = copy_bone( self.obj, name, mch(basename(name)) )

            # Adding to lists
            ctrl_chain    += [ctrl_bone]
            mch_chain     += [mch_bone]

        # Restoring org chain parenting
        eb[ org_bones[0] ].parent = eb[ root_parent_name ]
        for bone in org_bones[1:]:
            eb[bone].parent = eb[ org_bones[ org_bones.index(bone) - 1 ] ]

        # Parenting the master bone to the first org's parent
        ctrl_bone_master = eb[ master_name ]
        ctrl_bone_master.parent = eb[ root_parent_name ]

        # Parenting chain bones
        for i in range(len(org_bones)):
            # Edit bone references
            ctrl_bone_e    = eb[ctrl_chain[i]]
            mch_bone_e     = eb[mch_chain[i]]

            if i == 0:
                # First mch bone
                mch_bone_e.parent = eb[org_bones[i]].parent
                mch_bone_e.use_connect  = False
                # First ctl bone
                ctrl_bone_e.parent      = mch_bone_e
                ctrl_bone_e.use_connect = False
            else:
                # Parenting mch bone
                mch_bone_e.parent      = eb[ctrl_chain[i-1]]
                mch_bone_e.use_connect = False
                # The rest
                ctrl_bone_e.parent         = mch_bone_e
                ctrl_bone_e.use_connect    = False

        bpy.ops.object.mode_set(mode ='OBJECT')

        pb = self.obj.pose.bones

        # Setting pose bones locks
        pb_master = pb[master_name]
        pb_master.lock_location = True,True,True
        pb_master.lock_scale = True,False,True

        # Pose settings
        for org, ctrl, mcha in zip(self.org_bones, ctrl_chain, mch_chain):
            # Constraining the org bones
            con           = pb[org].constraints.new('COPY_TRANSFORMS')
            con.target    = self.obj
            con.subtarget = ctrl

            # Constraining the mch bones
            if mch_chain.index(mcha) == 0:
                con              = pb[mcha].constraints.new('COPY_ROTATION')
                con.target       = self.obj
                con.subtarget    = master_name
                con.target_space = 'LOCAL'
                con.owner_space  = 'LOCAL'
            else:
                con              = pb[mcha].constraints.new('COPY_ROTATION')
                con.target       = self.obj
                con.subtarget    = master_name
                for i, prop in enumerate( [ 'use_x', 'use_y', 'use_z' ] ):
                    if self.params.primary_rotation_axis == ['X', 'Y', 'Z'][i]:
                        setattr( con, prop, True )
                    else:
                        setattr( con, prop, False )
                con.target_space = 'LOCAL'
                con.owner_space  = 'LOCAL'

            # Assigning shapes to control bones
            create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)

        # Create ctrl master widget
        w = create_widget(self.obj, master_name)
        if w is not None:
            mesh = w.data
            verts = [(0, 0, 0), (0, 1, 0), (0.05, 1, 0), (0.05, 1.1, 0), (-0.05, 1.1, 0), (-0.05, 1, 0)]
            if 'Z' in self.params.primary_rotation_axis:
                # Flip x/z coordinates
                temp = []
                for v in verts:
                    temp += [(v[2], v[1], v[0])]
                verts = temp
            edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 1)]
            mesh.from_pydata(verts, edges, [])
            mesh.update()


def add_parameters(params):
    """ Add the parameters of this rig type to the
        GameRigParameters PropertyGroup
    """
    items = [('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')]
    params.primary_rotation_axis = bpy.props.EnumProperty(items=items, name="Primary Rotation Axis", default='X')


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.label(text="Bend rotation axis:")
    r.prop(params, "primary_rotation_axis", text="")


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('palm.04.L')
    bone.head[:] = 0.0043, -0.0030, -0.0026
    bone.tail[:] = 0.0642, 0.0030, -0.0469
    bone.roll = -2.5155
    bone.use_connect = False
    bones['palm.04.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.01.L')
    bone.head[:] = 0.0642, 0.0030, -0.0469
    bone.tail[:] = 0.0825, 0.0039, -0.0679
    bone.roll = -2.3110
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.04.L']]
    bones['f_pinky.01.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.02.L')
    bone.head[:] = 0.0825, 0.0039, -0.0679
    bone.tail[:] = 0.0958, 0.0044, -0.0862
    bone.roll = -2.2257
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.01.L']]
    bones['f_pinky.02.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.03.L')
    bone.head[:] = 0.0958, 0.0044, -0.0862
    bone.tail[:] = 0.1023, 0.0046, -0.0997
    bone.roll = -2.0532
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.02.L']]
    bones['f_pinky.03.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['palm.04.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['f_pinky.01.L']]
    pbone.gamerig_type = 'gamerig.finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.gamerig_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_pinky.02.L']]
    pbone.gamerig_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_pinky.03.L']]
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
