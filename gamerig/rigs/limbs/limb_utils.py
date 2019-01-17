import bpy, re
from mathutils import Vector
from ...utils import MetarigError, mch, org, basename

bilateral_suffixes = ['.L','.R']


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
