import bpy
from mathutils import Vector
from rna_prop_ui import rna_idprop_ui_create
from ..utils import (
    copy_bone, put_bone,
    ctrlname, basename, mchname, connected_children_names,
    create_widget, move_bone_collection_to,
    MetarigError
)
from .widgets import create_sphere_widget, create_directed_circle_widget

class Rig:

    def __init__(self, obj, bone_name, metabone):
        """ Initialize torso rig and key rig properties
        """

        eb = obj.data.edit_bones

        self.obj          = obj
        self.org_bones    = [bone_name] + connected_children_names(obj, bone_name)
        self.params       = metabone.gamerig
        self.spine_length = sum( [ eb[b].length for b in self.org_bones ] )

        self.root_bone_parent = eb[ self.org_bones[0] ].parent.name if eb[ self.org_bones[0] ].parent else None
        
        # Check if user provided the positions of the neck and pivot
        if self.params.neck_pos and self.params.pivot_pos:
            self.neck_pos  = self.params.neck_pos
            self.pivot_pos = self.params.pivot_pos
        else:
            raise MetarigError(
                "GAMERIG ERROR: please specify neck and pivot bone positions"
            )

        # Check if neck is lower than pivot
        if self.params.neck_pos <= self.params.pivot_pos:
            raise MetarigError(
                "GAMERIG ERROR: Neck cannot be below or the same as pivot"
            )

        # TODO:
        # Limit neck_pos prop  to 1 --> num of bones - 1 (last is head)
        # Limit pivot_pos prop to 2 --> num of bones (must leave place for lower torso)

        neck_index  = self.neck_pos  - 1
        pivot_index = self.pivot_pos - 1

        self.stretchable_tweak = self.params.stretchable_tweak

        # Report error of user created less than the minimum of 4 bones for rig
        if len(self.org_bones) <= 4 or neck_index < 2 or pivot_index < 1:
            raise MetarigError(
                "GAMERIG ERROR: %s : invalid rig structure" % bone_name
            )


    def build_bone_structure( self ):
        """ Divide meta-rig into lists of bones according to torso rig anatomy:
            Neck --> Upper torso --> Lower torso
        """
        if self.pivot_pos and self.neck_pos:

            neck_index  = self.neck_pos  - 1
            pivot_index = self.pivot_pos - 1

            neck_bones        = self.org_bones[neck_index::]
            upper_torso_bones = self.org_bones[pivot_index:neck_index]
            lower_torso_bones = self.org_bones[:pivot_index]

            return {
                'neck'  : neck_bones,
                'upper' : upper_torso_bones,
                'lower' : lower_torso_bones,
            }

        else:
            return 'ERROR'

    def orient_bone( self, eb, axis, scale, reverse = False ):
        v = Vector((0,0,0))

        setattr(v,axis,scale)

        if reverse:
            tail_vec = v @ self.obj.matrix_world
            eb.head[:] = eb.tail
            eb.tail[:] = eb.head + tail_vec
        else:
            tail_vec = v @ self.obj.matrix_world
            eb.tail[:] = eb.head + tail_vec


    def create_pivot( self, pivot ):
        """ Create the pivot control and mechanism bones
        """
        org_bones  = self.org_bones
        pivot_name = org_bones[pivot-1]

        eb = self.obj.data.edit_bones

        # Create torso control bone
        ctrl_name  = copy_bone(self.obj, pivot_name, ctrlname('torso'))
        ctrl_eb    = eb[ ctrl_name ]

        self.orient_bone( ctrl_eb, 'y', self.spine_length / 2.5 )

        # Create mch_pivot
        mch_name = mchname('pivot')
        mch_name = copy_bone(self.obj, ctrl_name, mch_name)
        mch_eb   = eb[ mch_name ]

        mch_eb.length /= 4

        # Positioning pivot in a more usable location for animators
        pivot_loc = ( eb[ org_bones[0]].head + eb[ org_bones[0]].tail ) / 2

        put_bone( self.obj, ctrl_name, pivot_loc )

        return {
            'ctrl' : ctrl_name,
            'mch'  : mch_name
        }

    def create_neck( self, neck_bones ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        # Create neck control
        neck    = copy_bone( self.obj, neck_bones[0], ctrlname('neck') )
        neck_eb = eb[ neck ]

        # Neck spans all neck bones (except head)
        neck_eb.tail[:] = eb[ neck_bones[-1] ].head

        # Create head control
        head = copy_bone( self.obj, neck_bones[-1], ctrlname('head') )

        # MCH bones
        # Neck MCH stretch
        mch_str = copy_bone( self.obj, neck, mchname('STR-neck') )

        # Neck MCH rotation
        mch_neck = copy_bone(self.obj, neck, mchname('ROT-neck'))

        self.orient_bone( eb[mch_neck], 'y', self.spine_length / 10 )

        # Head MCH rotation
        mch_head = copy_bone(self.obj, head, mchname('ROT-head'))

        self.orient_bone( eb[mch_head], 'y', self.spine_length / 10 )

        twk,mch = [],[]

        # Intermediary bones
        for b in neck_bones[1:-1]: # All except 1st neck and (last) head
            mch_name = copy_bone( self.obj, b, mchname(b) )
            eb[mch_name].length /= 4

            mch.append(mch_name)

        # Tweak bones
        for b in neck_bones[:-1]: # All except last bone
            twk_name = copy_bone( self.obj, b, ctrlname("tweak_" + b) )

            eb[twk_name].length /= 2

            twk.append(twk_name)

        return {
            'ctrl_neck' : neck,
            'ctrl'      : head,
            'mch_str'   : mch_str,
            'mch_neck'  : mch_neck,
            'mch_head'  : mch_head,
            'mch'       : mch,
            'tweak'     : twk
        }


    def create_chest( self, chest_bones ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        # get total spine length

        # Create chest control bone
        chest = copy_bone(self.obj, chest_bones[0], ctrlname('chest'))
        self.orient_bone(eb[chest], 'y', self.spine_length / 3)

        # create chest mch_wgt
        mch_wgt = copy_bone(self.obj, chest_bones[-1], mchname('chest'))

        # Create mch and twk bones
        twk,mch = [],[]

        for b in chest_bones:
            mch_name = copy_bone(self.obj, b, mchname(b))
            self.orient_bone(eb[mch_name], 'y', self.spine_length / 10)

            twk_name = copy_bone(self.obj, b, ctrlname("tweak_" + b))
            eb[twk_name].length /= 2

            mch.append( mch_name )
            twk.append( twk_name )

        return {
            'ctrl'    : chest,
            'mch'     : mch,
            'tweak'   : twk,
            'mch_wgt' : mch_wgt
        }


    def create_hips( self, hip_bones ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        # Create hips control bone
        hips = copy_bone(self.obj, hip_bones[-1], ctrlname('hips'))
        self.orient_bone(eb[hips], 'y', self.spine_length / 4, reverse = True)

        # create hips mch_wgt
        mch_wgt = copy_bone(self.obj, hip_bones[0], mchname('hips'))

        # Create mch and tweak bones
        twk,mch = [],[]
        for b in hip_bones:
            mch_name = copy_bone(self.obj, b, mchname(b))
            self.orient_bone(eb[mch_name], 'y', self.spine_length / 10, reverse = True)

            twk_name = copy_bone(self.obj, b, ctrlname("tweak_" + b))

            eb[twk_name].length /= 2

            mch.append( mch_name )
            twk.append( twk_name )

        return {
            'ctrl'   : hips,
            'mch'    : mch,
            'tweak'  : twk,
            'mch_wgt': mch_wgt
        }


    def parent_bones( self, bones ):
        org_bones = self.org_bones

        eb = self.obj.data.edit_bones

        # Parent deform bones
        for i,b in enumerate(org_bones):
            if i == 0:
                if self.root_bone_parent:
                    eb[b].parent = eb[self.root_bone_parent]
            else:
                eb[b].parent      = eb[org_bones[i-1]] # to previous
                eb[b].use_connect = True

        # Parent control bones
        # Torso control => orginal root
        eb[ bones['pivot']['ctrl'] ].parent = eb[ org_bones[0] ].parent

        # Head control => MCH-rotation_head
        eb[ bones['neck']['ctrl'] ].parent = eb[ bones['neck']['mch_head'] ]

        # MCH stretch => neck ctrl
        eb[ bones['neck']['mch_str'] ].parent = eb[ bones['neck']['ctrl_neck'] ]

        # Neck control => MCH-rotation_neck
        eb[ bones['neck']['ctrl_neck'] ].parent = eb[ bones['neck']['mch_neck'] ]

        # Parent hips and chest controls to torso
        eb[ bones['chest']['ctrl'] ].parent = eb[ bones['pivot']['ctrl'] ]
        eb[ bones['hips']['ctrl'] ].parent  = eb[ bones['pivot']['ctrl'] ]

        # Parent mch bones
        # Neck mch
        eb[ bones['neck']['mch_head'] ].parent = eb[ bones['neck']['ctrl_neck'] ]

        parent = eb[ bones['neck']['mch_str'] ]
        for i,b in enumerate([ eb[n] for n in bones['neck']['mch'] ]):
            b.parent = parent

        # Chest mch bones and neck mch
        chest_mch = bones['chest']['mch'] + [ bones['neck']['mch_neck'] ]
        for i,b in enumerate(chest_mch):
            if i == 0:
                eb[b].parent = eb[ bones['pivot']['ctrl'] ]
            else:
                eb[b].parent = eb[ chest_mch[i-1] ]

        # Hips mch bones
        for i,b in enumerate( bones['hips']['mch'] ):
            if i == len(bones['hips']['mch']) - 1:
                eb[b].parent = eb[ bones['pivot']['ctrl'] ]
            else:
                eb[b].parent = eb[ bones['hips']['mch'][i+1] ]

        # mch pivot
        eb[ bones['pivot']['mch'] ].parent = eb[ bones['chest']['mch'][0] ]

        # MCH widgets
        eb[ bones['chest']['mch_wgt'] ].parent = eb[ bones['chest']['mch'][-1] ]
        eb[ bones['hips' ]['mch_wgt'] ].parent = eb[ bones['hips' ]['mch'][0 ] ]

        # Tweaks

        # Neck tweaks
        for i,twk in enumerate( bones['neck']['tweak'] ):
            if i == 0:
                eb[ twk ].parent = eb[ bones['neck']['ctrl_neck'] ]
            else:
                eb[ twk ].parent = eb[ bones['neck']['mch'][i-1] ]

        # Chest tweaks
        for twk,mch in zip( bones['chest']['tweak'], bones['chest']['mch'] ):
            if bones['chest']['tweak'].index( twk ) == 0:
                eb[ twk ].parent = eb[ bones['pivot']['mch'] ]
            else:
                eb[ twk ].parent = eb[ mch ]

        # Hips tweaks
        for i,twk in enumerate(bones['hips']['tweak']):
            if i == 0:
                eb[twk].parent = eb[ bones['hips']['mch'][i] ]
            else:
                eb[twk].parent = eb[ bones['hips']['mch'][i-1] ]


    def make_constraint( self, bone, constraint ):
        pb = self.obj.pose.bones

        owner_pb     = pb[bone]
        const        = owner_pb.constraints.new( constraint['constraint'] )
        const.target = self.obj

        # filter contraint props to those that actually exist in the currnet
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            setattr( const, p, constraint[p] )


    def constrain_bones( self, bones ):
        # MCH bones

        # head and neck MCH bones
        for b in [ bones['neck']['mch_head'], bones['neck']['mch_neck'] ]:
            self.make_constraint( b, {
                'constraint': 'COPY_ROTATION',
                'subtarget' : bones['pivot']['ctrl'],
            } )
            self.make_constraint( b, {
                'constraint': 'COPY_SCALE',
                'subtarget' : bones['pivot']['ctrl'],
            } )

        # Neck MCH Stretch
        self.make_constraint( bones['neck']['mch_str'], {
            'constraint': 'DAMPED_TRACK',
            'subtarget' : bones['neck']['ctrl'],
        })

        # Intermediary mch bones
        intermediaries = [ bones['neck'], bones['chest'], bones['hips'] ]

        for i,l in enumerate(intermediaries):
            mch     = l['mch']
            factor  = float( 1 / len( l['tweak'] ) )

            for j,b in enumerate(mch):
                if i == 0:
                    nfactor = float( (j + 1) / len( mch ) )
                    self.make_constraint( b, {
                        'constraint': 'COPY_ROTATION',
                        'subtarget' : l['ctrl'],
                        'influence' : nfactor
                    } )
                else:
                    self.make_constraint( b, {
                        'constraint'  : 'COPY_TRANSFORMS',
                        'subtarget'   : l['ctrl'],
                        'influence'   : factor,
                        'owner_space' : 'LOCAL',
                        'target_space': 'LOCAL'
                    } )


        # MCH pivot
        self.make_constraint( bones['pivot']['mch'], {
            'constraint'  : 'COPY_TRANSFORMS',
            'subtarget'   : bones['hips']['mch'][-1],
            'owner_space' : 'LOCAL',
            'target_space': 'LOCAL'
        })

        # deform bones
        tweaks =  bones['hips']['tweak'] + bones['chest']['tweak'] + bones['neck']['tweak'] + [ bones['neck']['ctrl'] ]

        for d,t in zip(self.org_bones, tweaks):
            tidx = tweaks.index(t)

            self.make_constraint( d, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : t
            })

            if tidx != len(tweaks) - 1:
                self.make_constraint( d, {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : tweaks[ tidx + 1 ],
                })

                if self.stretchable_tweak:
                    self.make_constraint( d, {
                        'constraint'  : 'STRETCH_TO',
                        'subtarget'   : tweaks[ tidx + 1 ],
                    })

        pb = self.obj.pose.bones


    def create_drivers( self, bones ):
        pb = self.obj.pose.bones

        # Setting the torso's props
        torso = pb[ bones['pivot']['ctrl'] ]

        props  = [ 'Head Follow', 'Neck Follow' ]
        owners = [ bones['neck']['mch_head'], bones['neck']['mch_neck'] ]

        for pname in props:
            if pname == 'Neck Follow':
                torso[pname] = 0.5
            else:
                torso[pname] = 0.0
            rna_idprop_ui_create( torso, pname, default=0.0, description = pname, overridable=True )

        # driving the follow rotation switches for neck and head
        for bone, prop, in zip( owners, props ):
            # Add driver to copy rotation constraint
            drv = pb[ bone ].constraints[ 0 ].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = prop.replace(' ', '_').lower()
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = torso.path_from_id() + '['+ '"' + prop + '"' + ']'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]

            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

        if self.stretchable_tweak:
            # Add driver to stretch constraint
            tweaks =  bones['hips']['tweak'] + bones['chest']['tweak'] + bones['neck']['tweak'] + [ bones['neck']['ctrl'] ]
            for bone, t in zip(self.org_bones, tweaks):
                rna_idprop_ui_create( pb[t], 'Tweak Stretch', default=1.0, description='Tweak Stretch', overridable=True )

                tidx = tweaks.index(t)
                if tidx != len(tweaks) - 1:
                    drv = pb[ bone ].constraints[ 'Stretch To' ].driver_add("influence").driver
                    drv.type = 'SUM'

                    var = drv.variables.new()
                    var.name = 'tweak_stretch'
                    var.type = "SINGLE_PROP"
                    var.targets[0].id = self.obj
                    var.targets[0].data_path = pb[t].path_from_id() + '["Tweak Stretch"]'


    def locks_and_widgets( self, bones ):
        pb = self.obj.pose.bones

        # Locks
        tweaks =  bones['neck']['tweak'] + bones['chest']['tweak'] + bones['hips']['tweak']

        # Tweak bones locks
        for bone in tweaks:
            pb[bone].rotation_mode = 'ZXY'
            pb[bone].lock_rotation = True, False, True
            pb[bone].lock_scale    = False, True, False

        # Widgets

        # Assigning a widget to torso bone
        create_torso_widget(self.obj, bones['pivot']['ctrl'])

        # Assigning widgets to control bones
        gen_ctrls = [
            bones['neck']['ctrl_neck'],
            bones['chest']['ctrl'],
            bones['hips']['ctrl']
        ]

        for bone in gen_ctrls:
            create_directed_circle_widget(self.obj, bone, radius = 1.0, head_tail = 0.5)

        # Head widget
        create_directed_circle_widget(self.obj, bones['neck']['ctrl'], radius = 0.75, head_tail = 1.0)

        # place widgets on correct bones
        chest_widget_loc = pb[ bones['chest']['mch_wgt'] ]
        pb[ bones['chest']['ctrl'] ].custom_shape_transform = chest_widget_loc

        hips_widget_loc = pb[ bones['hips']['mch_wgt'] ]

        pb[ bones['hips']['ctrl'] ].custom_shape_transform = hips_widget_loc

        # Assigning widgets to tweak bones and bone collection
        for bone in tweaks:
            create_sphere_widget(self.obj, bone)

            move_bone_collection_to(self.obj, bone, self.params.tweak_bone_collection)


    def generate(self, context):

        # Torso Rig Anatomy:
        # Neck: all bones above neck point, last bone is head
        # Upper torso: all bones between pivot and neck start
        # Lower torso: all bones below pivot until tail point

        bone_chains = self.build_bone_structure()

        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in self.org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        if bone_chains != 'ERROR':

            # Create lists of bones and strip "ORG" from their names
            neck_bones        = [ basename(b) for b in bone_chains['neck' ] ]
            upper_torso_bones = [ basename(b) for b in bone_chains['upper'] ]
            lower_torso_bones = [ basename(b) for b in bone_chains['lower'] ]

            bones = {}

            bones['pivot'] = self.create_pivot( self.pivot_pos )
            bones['neck']  = self.create_neck( neck_bones )
            bones['chest'] = self.create_chest( upper_torso_bones )
            bones['hips']  = self.create_hips( lower_torso_bones )

            self.parent_bones(      bones )
            
            self.bones = bones


        controls = [
            bones['neck']['ctrl'], bones['neck']['ctrl_neck'], bones['chest']['ctrl'],
            bones['hips']['ctrl'], bones['pivot']['ctrl']
        ]

        # Create UI
        controls_string = ", ".join(["'" + x + "'" for x in controls])

        return f"""
controls = [{controls_string}]
if is_selected( controls ):
    layout.prop( pose_bones[ '{bones['pivot']['ctrl']}' ], '["Head Follow"]', text='Head Follow ({bones['pivot']['ctrl']})', slider = True )
    layout.prop( pose_bones[ '{bones['pivot']['ctrl']}' ], '["Neck Follow"]', text='Neck Follow ({bones['pivot']['ctrl']})', slider = True )
""" + (f"""
tweaks = {bones['hips']['tweak'] + bones['chest']['tweak'] + bones['neck']['tweak'] + [ bones['neck']['ctrl'] ]}
for tweak in tweaks:
    if is_selected( tweak ):
        layout.prop( pose_bones[ tweak ], '["Tweak Stretch"]', text='Tweak Stretch (' + tweak + ')', slider = True )
""" if self.stretchable_tweak else "") + f"""
# Torso Align Button
if is_selected( controls ):
    props = layout.operator(Torso_Align2Floor.bl_idname, text='Align To Floor ({self.org_bones[0]})', icon='SNAP_ON')
    props.head  = controls[0]
    props.neck  = controls[1]
    props.chest = controls[2]
    props.hips  = controls[3]
    props.pivot = controls[4]
    props = layout.operator(Torso_AlignYaw.bl_idname, text='Align Yaw ({self.org_bones[0]})', icon='SNAP_ON')
    props.head  = controls[0]
    props.neck  = controls[1]
    props.chest = controls[2]
    props.hips  = controls[3]
    props.pivot = controls[4]
"""


    def postprocess(self, context):
        self.constrain_bones(   self.bones )
        self.create_drivers(    self.bones )
        self.locks_and_widgets( self.bones )


def operator_script(rig_id):
    return '''

class Torso_Align2Floor(bpy.types.Operator):
    """ Align torso rig to horizontal plane.
    """
    bl_idname = "gamerig.torso_align_to_floor_{rig_id}"
    bl_label = "Align Pivot To Floor"
    bl_description = "Align pivot to horizontal plane"
    bl_options = {{'UNDO', 'INTERNAL'}}

    pivot : bpy.props.StringProperty(name="Pivot Name")
    hips  : bpy.props.StringProperty(name="Hips Name")
    chest : bpy.props.StringProperty(name="Chest Name")
    neck  : bpy.props.StringProperty(name="Neck Name")
    head  : bpy.props.StringProperty(name="Head Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            obj = context.active_object

            pivot = obj.pose.bones[self.pivot]
            hips  = obj.pose.bones[self.hips]
            chest = obj.pose.bones[self.chest]
            neck  = obj.pose.bones[self.neck]
            head  = obj.pose.bones[self.head]

            # Store original transform
            org_hips_mat = hips.matrix.copy()
            org_chest_mat = chest.matrix.copy()
            org_neck_mat = neck.matrix.copy()
            org_head_mat = head.matrix.copy()

            # Align pivot
            loc, rot, scl = pivot.matrix.decompose()
            euler = rot.to_euler('XYZ')
            euler.x = euler.y = 0.0
            rot = euler.to_quaternion()
            pivot_mat = get_pose_matrix_in_other_space(Matrix.LocRotScale(loc, rot, scl), pivot)
            set_pose_rotation(pivot, pivot_mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, pivot)

            # Match hips position
            mat = get_pose_matrix_in_other_space(org_hips_mat, hips)
            set_pose_rotation(hips, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, hips)

            # Match chest position
            mat = get_pose_matrix_in_other_space(org_chest_mat, chest)
            set_pose_rotation(chest, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, chest)

            # Match neck position
            mat = get_pose_matrix_in_other_space(org_neck_mat, neck)
            set_pose_rotation(neck, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, neck)

            # Match head position
            mat = get_pose_matrix_in_other_space(org_head_mat, head)
            set_pose_rotation(head, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, head)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Torso_AlignYaw(bpy.types.Operator):
    """ Align torso rig to horizontal plane.
    """
    bl_idname = "gamerig.torso_align_yaw_{rig_id}"
    bl_label = "Align Yaw"
    bl_description = "Align pivot to nearest vertial plane"
    bl_options = {{'UNDO', 'INTERNAL'}}

    pivot : bpy.props.StringProperty(name="Pivot Name")
    hips  : bpy.props.StringProperty(name="Hips Name")
    chest : bpy.props.StringProperty(name="Chest Name")
    neck  : bpy.props.StringProperty(name="Neck Name")
    head  : bpy.props.StringProperty(name="Head Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            obj = context.active_object

            pivot = obj.pose.bones[self.pivot]
            hips  = obj.pose.bones[self.hips]
            chest = obj.pose.bones[self.chest]
            neck  = obj.pose.bones[self.neck]
            head  = obj.pose.bones[self.head]

            # Store original transform
            org_hips_mat = hips.matrix.copy()
            org_chest_mat = chest.matrix.copy()
            org_neck_mat = neck.matrix.copy()
            org_head_mat = head.matrix.copy()

            # Align pivot
            loc, rot, scl = pivot.matrix.decompose()
            euler = rot.to_euler('XYZ')
            if euler.z >= 0.0:
                euler.z = floor((euler.z + radians(45)) / radians(90)) * radians(90)
            else:
                euler.z = -(floor((-euler.z + radians(45)) / radians(90)) * radians(90))

            rot = euler.to_quaternion()
            pivot_mat = get_pose_matrix_in_other_space(Matrix.LocRotScale(loc, rot, scl), pivot)
            set_pose_rotation(pivot, pivot_mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, pivot)

            # Match hips position
            mat = get_pose_matrix_in_other_space(org_hips_mat, hips)
            set_pose_rotation(hips, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, hips)

            # Match chest position
            mat = get_pose_matrix_in_other_space(org_chest_mat, chest)
            set_pose_rotation(chest, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, chest)

            # Match neck position
            mat = get_pose_matrix_in_other_space(org_neck_mat, neck)
            set_pose_rotation(neck, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, neck)

            # Match head position
            mat = get_pose_matrix_in_other_space(org_head_mat, head)
            set_pose_rotation(head, mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='POSE')
            insert_keyframe_by_mode(context, head)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Torso_Align2Floor)
classes.append(Torso_AlignYaw)

'''.format(rig_id=rig_id)


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.neck_pos = bpy.props.IntProperty(
        name        = 'Neck Position',
        default     = 5,
        min         = 0,
        description = 'Neck start position'
    )

    params.pivot_pos = bpy.props.IntProperty(
        name         = 'Pivot Position',
        default      = 2,
        min          = 0,
        description  = 'Position of the torso control and pivot point'
    )

    params.stretchable_tweak = bpy.props.BoolProperty(
        name        = "Stretchable Tweak",
        default     = True,
        description = "Allow stretch to tweak controllers"
    )

    # Setting up extra bone collection for the FK and tweak
    params.tweak_bone_collection = bpy.props.StringProperty(
        name        = "Tweak Bone Collection",
        description = "Bone collection for the tweak controls to be on",
        default     = "Torso (Tweak)"
    )


def create_torso_widget(rig, bone_name, size=1, bone_transform_name=None):
    """ Creates a torso cube widget.
    """
    obj = create_widget(rig, bone_name, bone_transform_name)
    if obj != None:
        verts = [(0.5*size, 0.5*size, 0.5*size), (0.5*size, -0.5*size, 0.5*size), (-0.5*size, -0.5*size, 0.5*size), (-0.5*size, 0.5*size, 0.5*size), (0.5*size, 0.5*size, -0.5*size), (0.5*size, -0.5*size, -0.5*size), (-0.5*size, -0.5*size, -0.5*size), (-0.5*size, 0.5*size, -0.5*size), (-0.049471*size, -0.54198*size, 0.4719*size), (0.047116*size, -0.54198*size, 0.4719*size), (-0.0002994*size, -0.59993*size, 0.4719*size), ]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7), (8, 9), (9, 10), (10, 8), ]
        faces = []

        mesh = obj.data
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        return obj
    else:
        return None


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""

    r = layout.row()
    r.prop(params, "neck_pos")

    r = layout.row()
    r.prop(params, "pivot_pos")

    r = layout.row()
    r.prop(params, "stretchable_tweak")

    r = layout.row()
    r.prop(params, "tweak_bone_collection")


def create_sample(obj):
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('hips')
    bone.head[:] = 0.0000, 0.0552, -0.0007
    bone.tail[:] = 0.0000, -0.0037, 0.2256
    bone.roll = 0.0000
    bone.use_connect = False
    bones['hips'] = bone.name
    bone = arm.edit_bones.new('waist')
    bone.head[:] = 0.0000, -0.0037, 0.2256
    bone.tail[:] = -0.0000, -0.0099, 0.3598
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['hips']]
    bones['waist'] = bone.name
    bone = arm.edit_bones.new('chest')
    bone.head[:] = -0.0000, -0.0099, 0.3598
    bone.tail[:] = -0.0000, -0.0045, 0.4748
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['waist']]
    bones['chest'] = bone.name
    bone = arm.edit_bones.new('upper_chest')
    bone.head[:] = -0.0000, -0.0045, 0.4748
    bone.tail[:] = 0.0000, 0.0114, 0.6476
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['chest']]
    bones['upper_chest'] = bone.name
    bone = arm.edit_bones.new('neck')
    bone.head[:] = 0.0000, 0.0114, 0.6476
    bone.tail[:] = 0.0000, -0.0247, 0.7707
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_chest']]
    bones['neck'] = bone.name
    bone = arm.edit_bones.new('head')
    bone.head[:] = 0.0000, -0.0247, 0.7707
    bone.tail[:] = 0.0000, -0.0247, 0.9690
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['neck']]
    bones['head'] = bone.name

    if not "Torso" in arm.collection.keys():
        arm.collection.new("Torso")
    if not "Torso (Tweak)" in obj.data.collection.keys():
        arm.collection.new("Torso (Tweak)")

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['hips']]
    pbone.gamerig.name = 'torso'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    obj.data.collection["Face"].assing(pbone)
    try:
        pbone.gamerig.pivot_pos = 2
    except AttributeError:
        pass
    try:
        pbone.gamerig.neck_pos = 5
    except AttributeError:
        pass
    try:
        pbone.gamerig.stretchable_tweak = True
    except AttributeError:
        pass
    try:
        pbone.gamerig.tweak_bone_collection = "Torso (Tweak)"
    except AttributeError:
        pass
    try:
        pbone.gamerig.chain_bone_controls = ""
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['waist']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    arm.collection["Face"].assing(pbone)
    pbone = obj.pose.bones[bones['chest']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    arm.collection["Face"].assing(pbone)
    pbone = obj.pose.bones[bones['upper_chest']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    arm.collection["Face"].assing(pbone)
    pbone = obj.pose.bones[bones['neck']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    arm.collection["Face"].assing(pbone)
    pbone = obj.pose.bones[bones['head']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    arm.collection["Face"].assing(pbone)

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
