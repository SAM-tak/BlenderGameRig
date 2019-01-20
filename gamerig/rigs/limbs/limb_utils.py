import bpy, re
from rna_prop_ui import rna_idprop_ui_prop_get
from mathutils import Vector
from ...utils import MetarigError, mch, org, basename, copy_bone, new_bone


def orient_bone( cls, eb, axis, scale = 1.0, reverse = False ):
    v = Vector((0,0,0))

    setattr(v,axis,scale)

    if reverse:
        tail_vec = v @ cls.obj.matrix_world
        eb.head[:] = eb.tail
        eb.tail[:] = eb.head + tail_vec
    else:
        tail_vec = v @ cls.obj.matrix_world
        eb.tail[:] = eb.head + tail_vec

    eb.roll = 0.0


def make_constraint( cls, bone, constraint ):
    bpy.ops.object.mode_set(mode = 'OBJECT')
    pb = cls.obj.pose.bones

    owner_pb = pb[bone]
    const    = owner_pb.constraints.new( constraint['constraint'] )

    constraint['target'] = cls.obj

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


def make_ik_follow_bone(cls, eb, ctrl):
    """ add IK Follow feature
    """
    if cls.root_bone:
        mch_ik_socket = copy_bone( cls.obj, cls.root_bone, mch('socket_' + ctrl) )
        eb[ mch_ik_socket ].length /= 4
        eb[ mch_ik_socket ].use_connect = False
        eb[ mch_ik_socket ].parent = None
        eb[ ctrl    ].parent = eb[ mch_ik_socket ]
        return mch_ik_socket


def setup_ik_follow(cls, pb, pb_master, mch_ik_socket):
    """ Add IK Follow constrain and property and driver
    """
    if cls.root_bone:
        make_constraint( cls, mch_ik_socket, {
            'constraint'   : 'COPY_TRANSFORMS',
            'subtarget'    : cls.root_bone,
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
        var.targets[0].id = cls.obj
        var.targets[0].data_path = pb_master.path_from_id() + '['+ '"' + prop.name + '"' + ']'
