import bpy, re
from mathutils import Vector
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    MetarigError, copy_bone, flip_bone, connected_children_names, find_root_bone,
    create_widget,
    basename, ctrlname, mchname, insert_before_first_period
)
from .widgets import (
    create_face_widget, create_eye_widget, create_eyes_widget, create_ear_widget, create_jaw_widget,
    create_upper_arc_widget, create_lower_arc_widget, create_left_arc_widget, create_right_arc_widget
)


def mch_target(name):
    """ Prepends the MCH_PREFIX to a name if it doesn't already have
        it, and returns it.
    """
    if name:
        if name.startswith(mchname('target_')):
            return name
        else:
            return mchname('target_' + name)

class Rig:

    def __init__(self, obj, bone_name, metabone):
        self.obj = obj

        params = metabone.gamerig

        # Abstruct bone name map
        self.abs_name_map = { 'face' : bone_name }
        self.tail_mid_map = {}

        root = self.obj.data.bones[bone_name]
        self.add_chain_to_abs_name_map(root,                 'nose')
        self.add_chain_to_abs_name_map(root,                 'lip.T.L')
        self.add_chain_to_abs_name_map(root,                 'lip.T.R')
        self.add_chain_to_abs_name_map(root,                 'lip.B.L')
        self.add_chain_to_abs_name_map(root,                 'lip.B.R')
        c = self.add_chain_to_abs_name_map(root,             'jaw')
        self.add_chain_to_abs_name_map(c if c else root,     'chin')
        self.add_chain_to_abs_name_map(root,                 'ear.L')
        self.add_chain_to_abs_name_map(root,                 'ear.R')
        c = self.add_chain_to_abs_name_map(root,             'lid.T.L')
        self.add_chain_to_abs_name_map(c if c else root,     'lid.B.L')
        c = self.add_chain_to_abs_name_map(root,             'lid.T.R')
        self.add_chain_to_abs_name_map(c if c else root,     'lid.B.R')
        self.add_chain_to_abs_name_map(root,                 'brow.B.L')
        self.add_chain_to_abs_name_map(root,                 'brow.B.R')
        c = self.add_chain_to_abs_name_map(root,             'temple.L')
        c = self.add_chain_to_abs_name_map(c if c else root, 'jaw.L')
        c = self.add_chain_to_abs_name_map(c if c else root, 'chin.L')
        c = self.add_chain_to_abs_name_map(c if c else root, 'cheek.B.L')
        self.add_chain_to_abs_name_map(c if c else root,     'brow.T.L')
        c = self.add_chain_to_abs_name_map(root,             'temple.R')
        c = self.add_chain_to_abs_name_map(c if c else root, 'jaw.R')
        c = self.add_chain_to_abs_name_map(c if c else root, 'chin.R')
        c = self.add_chain_to_abs_name_map(c if c else root, 'cheek.B.R')
        self.add_chain_to_abs_name_map(c if c else root,     'brow.T.R')
        self.add_chain_to_abs_name_map(root,                 'eye.L')
        self.add_chain_to_abs_name_map(root,                 'eye.R')
        c = self.add_chain_to_abs_name_map(root,             'cheek.T.L')
        self.add_chain_to_abs_name_map(c if c else root,     'nose.L')
        c = self.add_chain_to_abs_name_map(root,             'cheek.T.R')
        self.add_chain_to_abs_name_map(c if c else root,     'nose.R')
        self.add_chain_to_abs_name_map(root,                 'tongue')

        self.org_bones   = list(self.abs_name_map.keys())

        if len(self.org_bones) < 2:
            raise MetarigError("GAMERIG ERROR: Bone '%s': Face rig has no valid child bones. face rig require specific name for child bones." % bone_name)

        self.face_length = obj.data.edit_bones[ bone_name ].length
        self.params      = params

        if params.primary_layers_extra:
            self.primary_layers = list(params.primary_layers)
        else:
            self.primary_layers = None

        if params.secondary_layers_extra:
            self.secondary_layers = list(params.secondary_layers)
        else:
            self.secondary_layers = None

    def add_chain_to_abs_name_map(self, root, name, depth=0):
        child = next((b for b in root.children if b.name.startswith(name)), None)
        if child:
            if depth == 0:
                self.abs_name_map[name] = child.name
            else:
                self.abs_name_map[name + '.%03d' % depth] = child.name
            return self.add_chain_to_abs_name_map(child, name, depth + 1)
        elif depth > 0:
            self.tail_mid_map[name] = [name + '.%03d' % (depth - 1) if depth > 1 else name, name + '.%03d' % (depth / 2) if depth > 1 else name, depth]
        return root

    number_suffix_patter = re.compile(r'.+\.(\d\d\d)$')

    @classmethod
    def get_number_suffix(cls, bonename):
        match = cls.number_suffix_patter.match(bonename)
        return int(match.group(1)) if match else None
    
    def make_unique_basebonename(self, bonename):
        if bonename in self.abs_name_map.keys():
            num = self.get_number_suffix(bonename)
            return self.make_unique_basebonename(bonename[:-3] + ('%03d' % (num + 1)) if num else bonename + '.001')
        else:
            return bonename

    def copy_bone(self, obj, bone_name, assign_name):
        assign_name = self.make_unique_basebonename(assign_name) if assign_name else bone_name
        ret = copy_bone(obj, self.rbn(bone_name), assign_name)
        self.abs_name_map[assign_name] = ret
        return assign_name

    def rbn(self, absname):
        """ return real bone name
        """
        # if absname not in self.abs_name_map:
        #     raise MetarigError("gamerig.face.rbn(): bone base name '%s' not found" % absname)
        return self.abs_name_map[absname]

    def midctrlname(self, name):
        return ctrlname(self.tail_mid_map[name][1]) if name in self.abs_name_map else None

    def tailctrlname(self, name):
        return ctrlname(name + '.%03d' % self.tail_mid_map[name][2]) if name in self.abs_name_map else None

    def symmetrical_split( self, bones ):
        # RE pattern match right or left parts
        # match the letter "L" (or "R"), followed by an optional dot (".")
        # and 0 or more digits at the end of the the string
        left_pattern  = re.compile(r'[\._ ]L(\.\d+)?$')
        right_pattern = re.compile(r'[\._ ]R(\.\d+)?$')

        left  = sorted( [ name for name in bones if left_pattern.search( name )  ] )
        right = sorted( [ name for name in bones if right_pattern.search( name ) ] )

        return left, right


    def create_ctrl( self, bones ):
        org_bones = self.org_bones
        rbn = self.rbn

        ret = {}

        ## create control bones
        eb = self.obj.data.edit_bones

        nose_master = None
        earL_ctrl_name = None
        earR_ctrl_name = None
        jaw_ctrl_name = None
        tongue_ctrl_name = None

        face_e = eb[rbn('face')]

        # eyes ctrls
        eye_master_names = []
        if 'eyes' in bones and len(bones['eyes']) > 1:
            eyeL_e = eb[ rbn(bones['eyes'][0]) ]
            eyeR_e = eb[ rbn(bones['eyes'][1]) ]

            distance = ( eyeL_e.head - eyeR_e.head )
            distance = distance.cross( (0, 0, 1) )
            eye_length = eyeL_e.length

            eyeL_ctrl_name = ctrlname( bones['eyes'][0] )
            eyeR_ctrl_name = ctrlname( bones['eyes'][1] )

            eyeL_ctrl_name = self.copy_bone( self.obj, bones['eyes'][0],  eyeL_ctrl_name  )
            eyeR_ctrl_name = self.copy_bone( self.obj, bones['eyes'][1],  eyeR_ctrl_name  )
            eyes_ctrl_name = self.copy_bone( self.obj, bones['eyes'][0], ctrlname('eyes') )

            eyeL_e = eb[ rbn(bones['eyes'][0]) ] # 'cause cache was invalidated by new bones were created.
            eyeR_e = eb[ rbn(bones['eyes'][1]) ]
            eyeL_ctrl_e = eb[ rbn(eyeL_ctrl_name) ]
            eyeR_ctrl_e = eb[ rbn(eyeR_ctrl_name) ]
            eyes_ctrl_e = eb[ rbn(eyes_ctrl_name) ]

            eyeL_ctrl_e.head    = eyeL_e.tail + distance
            eyeR_ctrl_e.head    = eyeR_e.tail + distance
            eyes_ctrl_e.head[:] =  ( eyeL_ctrl_e.head + eyeR_ctrl_e.head ) / 2

            for bone in ( eyeL_ctrl_e, eyeR_ctrl_e, eyes_ctrl_e ):
                bone.tail[:] = bone.head + Vector( [ 0, 0, eye_length * 0.75 ] )

            eyes_ctrl_e.length = (eyeL_ctrl_e.head - eyes_ctrl_e.head).length * 0.62

            eyeL_ctrl_e.align_roll(face_e.z_axis)
            eyeR_ctrl_e.align_roll(face_e.z_axis)
            eyes_ctrl_e.align_roll(face_e.z_axis)

            ## Widget for transforming the both eyes
            for bone in bones['eyes']:
                if bone in self.abs_name_map:
                    eye_master = self.copy_bone(self.obj, bone, ctrlname(insert_before_first_period(bone, '_master')))
                    eye_master_names.append( eye_master )
            
            ret['eyes'] = [eyeL_ctrl_name, eyeR_ctrl_name, eyes_ctrl_name] + eye_master_names

        ## turbo: adding a nose master for transforming the whole nose
        if 'nose' in self.abs_name_map:
            nose_master = self.copy_bone(self.obj, self.tail_mid_map['nose'][1], ctrlname('nose_master'))
            eb[rbn(nose_master)].use_connect = False
            eb[rbn(nose_master)].parent = None
            eb[rbn(nose_master)].tail = eb[rbn(nose_master)].head + face_e.z_axis * (self.face_length / -7)
            eb[rbn(nose_master)].roll = 0
            ret['nose'] = [nose_master]

        # ears ctrls
        if 'ears' in bones and bones['ears']:
            earL_name = bones['ears'][0]
            earL_ctrl_name = self.copy_bone( self.obj, bones['ears'][0], ctrlname(earL_name) )
            if len(bones['ears']) > 1:
                earR_name = bones['ears'][1]
                earR_ctrl_name = self.copy_bone( self.obj, bones['ears'][1], ctrlname(earR_name) )
                ret['ears'] = [ earL_ctrl_name, earR_ctrl_name ]
            else:
                ret['ears'] = [ earL_ctrl_name ]

        # jaw ctrl
        if 'jaw' in bones:
            if len(bones['jaw']) == 3:
                jaw_ctrl_name = ctrlname(insert_before_first_period(bones['jaw'][2], '_master'))
                jaw_ctrl_name = self.copy_bone( self.obj, bones['jaw'][2], jaw_ctrl_name )

                jawL_org_e = eb[ rbn(bones['jaw'][0]) ]
                jawR_org_e = eb[ rbn(bones['jaw'][1]) ]
                jaw_org_e  = eb[ rbn(bones['jaw'][2]) ]

                eb[ rbn(jaw_ctrl_name) ].head[:] = ( jawL_org_e.head + jawR_org_e.head ) / 2
                if abs( eb[ rbn(jaw_ctrl_name) ].y_axis.dot( face_e.z_axis ) ) > 1e-10:
                    eb[ rbn(jaw_ctrl_name) ].align_roll(-face_e.z_axis)
                else:
                    eb[ rbn(jaw_ctrl_name) ].align_roll(-face_e.y_axis)
                
                ret['jaw'] = [ jaw_ctrl_name ]
            elif len(bones['jaw']) == 1:
                jaw_ctrl_name = ctrlname(insert_before_first_period(bones['jaw'][0], '_master'))
                jaw_ctrl_name = self.copy_bone( self.obj, bones['jaw'][0], jaw_ctrl_name )
                jaw_org_e  = eb[ rbn(bones['jaw'][0]) ]
                
                ret['jaw'] = [ jaw_ctrl_name ]

        # tongue ctrl
        if 'tongue' in bones and bones['tongue']:
            tongue_org  = bones['tongue'].pop()
            tongue_name = insert_before_first_period( tongue_org, '_master' )

            tongue_ctrl_name = self.copy_bone( self.obj, tongue_org, ctrlname(tongue_name) )

            flip_bone( self.obj, rbn(tongue_ctrl_name) )
            eb[tongue_ctrl_name].align_roll(eb[tongue_org].z_axis)

            ret['tongue'] = [ tongue_ctrl_name ]
        
        self.eye_master_names = eye_master_names
        self.nose_master = nose_master
        self.earL_ctrl_name = earL_ctrl_name
        self.earR_ctrl_name = earR_ctrl_name
        self.jaw_ctrl_name = jaw_ctrl_name
        self.tongue_ctrl_name = tongue_ctrl_name

        return ret

    def create_ctrl_widget(self, ret):
        rbn = self.rbn

        ## Assign widgets
        # Assign each eye widgets
        if 'eyes' in ret:
            create_eye_widget( self.obj, rbn(ret['eyes'][0]) )
            create_eye_widget( self.obj, rbn(ret['eyes'][1]) )

            # Assign eyes widgets
            create_eyes_widget( self.obj, rbn(ret['eyes'][2]) )

        # Assign each eye_master widgets
        for master in self.eye_master_names:
            create_square_widget(self.obj, rbn(master))

        # Assign nose_master widget
        if 'nose' in ret:
            create_square_widget( self.obj, rbn(self.nose_master), size = 1 )

        # Assign ears widget
        if 'ears' in ret:
            create_ear_widget( self.obj, rbn(self.earL_ctrl_name) )
            create_ear_widget( self.obj, rbn(self.earR_ctrl_name) )

        # Assign jaw widget
        if 'jaw' in ret:
            create_jaw_widget( self.obj, rbn(self.jaw_ctrl_name) )

        # Assign tongue widget ( using the jaw widget )
        if 'tongue' in ret:
            create_jaw_widget( self.obj, rbn(self.tongue_ctrl_name) )


    def create_tweak( self, bones, uniques, tails ):
        org_bones = self.org_bones
        rbn = self.rbn

        ## create tweak bones
        eb = self.obj.data.edit_bones

        face_e = eb[rbn('face')]

        tweaks = []

        self.primary_tweaks = [ ctrlname('chin'), ctrlname('lip.B'), ctrlname('lip.T'), ctrlname('lips.L'), ctrlname('lips.R') ]

        for i in (
            'lid.B.L', 'lid.T.L', 'lid.B.R', 'lid.T.R',
            'brow.T.L', 'brow.B.L', 'brow.T.R', 'brow.B.R',
            'cheek.B.L', 'cheek.B.R',
            'lip.B.L', 'lip.T.L', 'lip.B.R', 'lip.T.R',
            'nose', 'nose.L', 'nose.R'
        ):
            if i in self.abs_name_map:
                self.primary_tweaks.append(self.midctrlname(i))

        for bone in bones + list( uniques.keys() ):
            if bone in self.abs_name_map:
                tweak_name = ctrlname( bone )

                if tweak_name in self.primary_tweaks and not self.primary_layers:
                    continue
                if not tweak_name in self.primary_tweaks and not self.secondary_layers:
                    continue

                # pick name for unique bone from the uniques dictionary
                if bone in list( uniques.keys() ):
                    tweak_name = ctrlname( uniques[bone] )

                tweak_name = self.copy_bone( self.obj, bone, tweak_name )
                eb[ rbn(tweak_name) ].use_connect = False
                eb[ rbn(tweak_name) ].parent      = None

                tweaks.append( tweak_name )

                eb[ rbn(tweak_name) ].tail[:] = eb[ rbn(tweak_name) ].head + Vector(( 0, 0, self.face_length / 7 ))
                if ctrlname('lip.T') == tweak_name or ctrlname('lip.B') == tweak_name:
                    eb[ rbn(tweak_name) ].align_roll( -face_e.z_axis )
                else:
                    eb[ rbn(tweak_name) ].align_roll( eb[ rbn(bone) ].z_axis )

                # create tail bone
                if bone in tails:
                    if 'lip.T.L' in bone:
                        tweak_name = self.copy_bone( self.obj, bone, ctrlname('lips.L') )
                    elif 'lip.T.R' in bone:
                        tweak_name = self.copy_bone( self.obj, bone, ctrlname('lips.R') )
                    else:
                        tweak_name = self.copy_bone( self.obj, bone, tweak_name )

                    eb[ rbn(tweak_name) ].use_connect = False
                    eb[ rbn(tweak_name) ].parent      = None

                    eb[ rbn(tweak_name) ].head    = eb[ rbn(bone) ].tail
                    eb[ rbn(tweak_name) ].tail[:] = eb[ rbn(tweak_name) ].head + Vector(( 0, 0, self.face_length / 7 ))

                    eb[ rbn(tweak_name) ].align_roll( eb[ rbn(bone) ].z_axis )

                    tweaks.append( tweak_name )

        return { 'all' : tweaks }


    def create_tweak_widget( self, tweaks ):
        pb = self.obj.pose.bones
        rbn = self.rbn

        for bone in tweaks:
            if bone in self.abs_name_map:
                if bone in self.primary_tweaks:
                    if self.primary_layers:
                        pb[rbn(bone)].bone.layers = self.primary_layers
                    size = 1
                else:
                    if self.secondary_layers:
                        pb[rbn(bone)].bone.layers = self.secondary_layers
                    size = 0.7
                
                if bone == ctrlname('lid.B.L') or bone == ctrlname('lid.T.R') or bone == ctrlname('lips.R'):
                    create_left_arc_widget( self.obj, rbn(bone), size = size )
                elif bone == ctrlname('lid.B.R') or bone == ctrlname('lid.T.L') or bone == ctrlname('lips.L'):
                    create_right_arc_widget( self.obj, rbn(bone), size = size )
                elif bone.startswith(ctrlname('lid.T.')) or bone == ctrlname('lip.T') or bone.startswith(ctrlname('lip.T.')):
                    create_upper_arc_widget( self.obj, rbn(bone), size = size )
                elif bone.startswith(ctrlname('lid.B.')) or bone == ctrlname('lip.B') or bone.startswith(ctrlname('lip.B.')):
                    create_lower_arc_widget( self.obj, rbn(bone), size = size )
                else:
                    create_face_widget( self.obj, rbn(bone), size = size * 0.8 )


    def all_controls( self ):
        org_bones = self.org_bones

        org_tongue_bones  = sorted([ bone for bone in org_bones if 'tongue' in bone ])

        org_to_ctrls = {
            'eyes'   : [ 'eye.L',   'eye.R'        ],
            'ears'   : [ 'ear.L',   'ear.R'        ],
            'jaw'    : [ 'jaw.L',   'jaw.R', 'jaw' ],
            'teeth'  : [ 'teeth.T', 'teeth.B'      ]
        }

        if org_tongue_bones and len(org_tongue_bones) > 0:
            org_to_ctrls['tongue'] = [ org_tongue_bones[0] ]

        org_to_ctrls = { key : [ bone for bone in org_to_ctrls[key] if bone in org_bones ] for key in org_to_ctrls.keys() }

        tweak_unique = {
            'lip.T.L' : ctrlname('lip.T'),
            'lip.B.L' : ctrlname('lip.B')
        }

        tweak_exceptions = [ bone for bone in org_bones if 'temple' in bone ]

        tweak_tail =  [ self.tail_mid_map[i][0] for i in ('brow.B.L', 'brow.B.R', 'nose', 'chin', 'lip.T.L', 'lip.T.R', 'tongue') if i in self.tail_mid_map ]

        tweak_exceptions += [ 'lip.T.R', 'lip.B.R', 'ear.L.001', 'ear.R.001' ]
        tweak_exceptions += list(tweak_unique.keys())
        tweak_exceptions += [
            'face', 'cheek.T.L', 'cheek.T.R', 'cheek.B.L', 'cheek.B.R',
            'ear.L', 'ear.R', 'eye.L', 'eye.R'
        ]

        tweak_exceptions += org_to_ctrls.keys()
        tweak_exceptions += org_to_ctrls['teeth']

        if 'tongue' in tweak_exceptions:
            tweak_exceptions.pop( tweak_exceptions.index('tongue') )
        if 'jaw' in tweak_exceptions:
            tweak_exceptions.pop( tweak_exceptions.index('jaw')    )

        tweak_exceptions = [ bone for bone in tweak_exceptions if bone in self.abs_name_map ]

        org_to_tweak = sorted( [ bone for bone in org_bones if bone not in tweak_exceptions ] )

        ctrls  = self.create_ctrl( org_to_ctrls )
        tweaks = self.create_tweak( org_to_tweak, tweak_unique, tweak_tail )

        return { 'ctrls' : ctrls, 'tweaks' : tweaks }, tweak_unique


    def create_mch( self, jaw_ctrl, tongue_ctrl, chin_ctrl ):
        org_bones = self.org_bones
        rbn = self.rbn
        eb = self.obj.data.edit_bones

        # Create eyes mch bones
        eyes = sorted([ bone for bone in org_bones if 'eye' in bone ])

        mch_bones = { eye : [] for eye in eyes }

        for eye in eyes:
            mch_name = self.copy_bone( self.obj, eye, mchname( eye ) )
            eb[ rbn(mch_name) ].use_connect = False
            eb[ rbn(mch_name) ].parent      = None

            mch_bones[ eye ].append( mch_name )

            mch_name = self.copy_bone( self.obj, eye, mch_name )
            eb[ rbn(mch_name) ].use_connect = False
            eb[ rbn(mch_name) ].parent      = None

            mch_bones[ eye ].append( mch_name )

            eb[ rbn(mch_name) ].head[:] = eb[ rbn(mch_name) ].tail
            eb[ rbn(mch_name) ].tail[:] = eb[ rbn(mch_name) ].head + Vector( ( 0, 0, 0.005 ) )

        # Create the eyes' parent mch
        face = next((bone for bone in org_bones if 'face' in bone), None)

        if eyes and len(eyes) > 0:
            mch_name = self.copy_bone( self.obj, face, mchname('eyes_parent') )
            eb[ rbn(mch_name) ].use_connect = False
            eb[ rbn(mch_name) ].parent      = None

            eb[ rbn(mch_name) ].length /= 4

            mch_bones['eyes_parent'] = [ mch_name ]

        # Create the lids' mch bones
        all_lids       = [ bone for bone in org_bones if 'lid' in bone ]
        lids_L, lids_R = self.symmetrical_split( all_lids )

        all_lids = [ lids_L, lids_R ]

        mch_bones['lids'] = []

        for i in range( len(eyes) ):
            if eyes[i] in self.abs_name_map:
                for bone in all_lids[i]:
                    mch_name = self.copy_bone( self.obj, eyes[i], mchname( bone ) )

                    eb[ rbn(mch_name) ].use_connect = False
                    eb[ rbn(mch_name) ].parent      = None

                    eb[ rbn(mch_name) ].tail[:] = eb[ rbn(bone) ].head

                    mch_bones['lids'].append( mch_name )

        if jaw_ctrl in self.abs_name_map:
            mch_bones['jaw'] = []

            length_subtractor = eb[ rbn(jaw_ctrl) ].length / 6
            # Create the jaw mch bones
            for i in range( 6 ):
                if i == 0:
                    mch_name = mchname( 'mouth_lock' )
                else:
                    mch_name = mchname( basename(jaw_ctrl) )

                mch_name = self.copy_bone( self.obj, jaw_ctrl, mch_name  )

                eb[ rbn(mch_name) ].use_connect = False
                eb[ rbn(mch_name) ].parent      = None

                eb[ rbn(mch_name) ].length = eb[ rbn(jaw_ctrl) ].length - length_subtractor * i
                eb[ rbn(mch_name) ].roll = eb[ rbn(jaw_ctrl) ].roll

                mch_bones['jaw'].append( mch_name )

        # Tongue mch bones
        if tongue_ctrl in self.abs_name_map:
            mch_bones['tongue'] = []

            # create mch bones for all tongue org_bones except the first one
            for bone in sorted([ org for org in org_bones if 'tongue' in org ])[1:]:
                mch_name = self.copy_bone( self.obj, tongue_ctrl, mchname( bone ) )

                eb[ rbn(mch_name) ].use_connect = False
                eb[ rbn(mch_name) ].parent      = None

                mch_bones['tongue'].append( mch_name )

            # Create the tongue parent mch
            if jaw_ctrl in self.abs_name_map:
                mch_name = self.copy_bone( self.obj, jaw_ctrl, mchname('tongue_parent') )
                eb[ rbn(mch_name) ].use_connect = False
                eb[ rbn(mch_name) ].parent      = None

                eb[ rbn(mch_name) ].length /= 4

                mch_bones['tongue_parent'] = [ mch_name ]

        # Create the chin parent mch
        if chin_ctrl in self.abs_name_map and jaw_ctrl in self.abs_name_map:
            mch_name = self.copy_bone( self.obj, jaw_ctrl, mchname('chin_parent') )
            eb[ rbn(mch_name) ].use_connect = False
            eb[ rbn(mch_name) ].parent      = None

            eb[ rbn(mch_name) ].length /= 4

            mch_bones['chin_parent'] = [ mch_name ]

            mch_name = self.copy_bone( self.obj, chin_ctrl, mchname('chin') )
            eb[ rbn(mch_name) ].use_connect = False
            eb[ rbn(mch_name) ].parent      = None

            mch_bones['chin'] = [ mch_name ]

        return mch_bones


    def create_mch_targets( self ):
        org_bones = self.org_bones
        rbn = self.rbn
        eb = self.obj.data.edit_bones

        mchts = []
        for i in org_bones:
            if i != 'face':
                mcht = self.copy_bone( self.obj, i, mch_target( i ) )
                eb[ rbn(mcht) ].use_connect = False
                eb[ rbn(mcht) ].parent      = None

                mchts.append(mcht)
        
        return mchts

    def parent_bones( self, all_bones, tweak_unique, mchts ):
        rbn = self.rbn
        eb = self.obj.data.edit_bones

        face_name = 'face'

        # Initially parenting all bones to the face org bone.
        for category, areas in all_bones.items():
            for area in areas:
                for bone in all_bones[category][area]:
                    eb[ rbn(bone) ].parent = eb[ rbn(face_name) ]

        mcht_prefix_len = len(mch_target('_')) - 1
        # Parent all the mch-target bones that have respective tweaks
        for bone in [ bone for bone in mchts if ctrlname( bone[mcht_prefix_len:] ) in all_bones['tweaks']['all'] ]:
            # the def and the matching org bone are parented to their corresponding tweak,
            # whose name is the same as that of the def bone, without the "MCH-target_" (first 11 chars)
            eb[ rbn(bone) ].parent = eb[ rbn( ctrlname( bone[mcht_prefix_len:] ) ) ]

        # Parent MCH-target eyes to corresponding mch bones
        for bone in [ bone for bone in mchts if 'eye' in bone ]:
            eb[ rbn(bone) ].parent = eb[ rbn( mchname( bone[mcht_prefix_len:] ) ) ]

        for lip_tweak in tweak_unique.values():
            # find the def bones that match unique lip_tweaks by slicing [4:-2]
            # example: 'lip.B' matches 'MCH-target_lip.B.R' and 'MCH-target_lip.B.L' if
            # you cut off the "MCH-target_" [mcht_prefix_len:] and the ".L" or ".R" [:-2]
            for bone in [ bone for bone in mchts if ctrlname( bone[mcht_prefix_len:-2] ) == lip_tweak ]:
                if lip_tweak in self.abs_name_map:
                    eb[ rbn( bone ) ].parent = eb[ rbn( lip_tweak ) ]

        # parent cheek bones top respetive tweaks
        lips  = [ ctrlname('lips.L'),   ctrlname('lips.R')   ]
        brows = [ ctrlname('brow.T.L'), ctrlname('brow.T.R') ]
        cheekB_defs = [ mch_target('cheek.B.L'), mch_target('cheek.B.R') ]
        cheekT_defs = [ mch_target('cheek.T.L'), mch_target('cheek.T.R') ]

        for lip, brow, cheekB, cheekT in zip( lips, brows, cheekB_defs, cheekT_defs ):
            if cheekB in self.abs_name_map and lip in self.abs_name_map:
                eb[ rbn( cheekB ) ].parent = eb[ rbn( lip ) ]
            if cheekT in self.abs_name_map and brow in self.abs_name_map:
                eb[ rbn( cheekT ) ].parent = eb[ rbn( brow ) ]

        # parent ear deform bones to their controls
        for ear_ctrl in ( 'ear.L', 'ear.R' ):
            for ear_mt in ( ear_ctrl, ear_ctrl + '.001' ):
                if ctrlname( ear_ctrl ) in self.abs_name_map and mch_target( ear_mt ) in mchts:
                    eb[ rbn( mch_target(ear_mt) ) ].parent = eb[ rbn( ctrlname( ear_ctrl ) ) ]

        # Parent eyelid deform bones (each lid def bone is parented to its respective MCH bone)
        for bone in [ bone for bone in mchts if 'lid' in bone ]:
            if bone in self.abs_name_map and mchname(bone[mcht_prefix_len:]) in self.abs_name_map:
                eb[ rbn( bone ) ].parent = eb[ rbn( mchname(bone[mcht_prefix_len:]) ) ]

        ## Parenting all mch bones
        if mchname('eyes_parent') in self.abs_name_map:
            eb[ rbn( mchname('eyes_parent') ) ].parent = None  # eyes_parent will be parented to root

        # parent all mch tongue bones to the jaw master control bone
        if 'tongue' in all_bones['mch']:
            for bone in all_bones['mch']['tongue']:
                eb[ rbn( bone ) ].parent = eb[ rbn( all_bones['ctrls']['jaw'][0] ) ]

        # parent tongue master to the tongue root mch bone
        if 'tongue' in all_bones['ctrls']:
            if 'tongue_parent' in all_bones['mch']:
                eb[ rbn( all_bones['ctrls']['tongue'][0] ) ].parent = eb[ rbn( all_bones['mch']['tongue_parent'][0] ) ]
            elif 'jaw' in all_bones['ctrls']:
                eb[ rbn( all_bones['ctrls']['tongue'][0] ) ].parent = eb[ rbn( all_bones['ctrls']['jaw'][0] ) ]

        ## Parenting the control bones

        # eyes
        if ctrlname('eyes') in self.abs_name_map:
            eb[ rbn( ctrlname('eyes') ) ].parent = eb[ rbn( mchname('eyes_parent') ) ]
            eyes = [bone for bone in all_bones['ctrls']['eyes'] if 'eyes' not in bone][0:2]

            for eye in eyes:
                if eye in self.abs_name_map:
                    eb[ rbn( eye ) ].parent = eb[ rbn( ctrlname('eyes') ) ]

            ## turbo: parent eye master bones to face
            for eye_master in eyes[2:]:
                eb[ rbn( eye_master ) ].parent = eb[ rbn( 'face' ) ]

        # Parent brow.b, eyes mch and lid tweaks and mch bones to masters
        tweaks = [b for b in all_bones['tweaks']['all'] if 'lid' in b or 'brow.B' in b]
        mchs = []
        if 'lids' in all_bones['mch']:
            mchs += all_bones['mch']['lids']
        if 'eye.R' in all_bones['mch']:
            mchs += all_bones['mch']['eye.R']
        if 'eye.L' in all_bones['mch']:
            mchs += all_bones['mch']['eye.L']

        everyone = tweaks + mchs

        left, right = self.symmetrical_split( everyone )

        for l in left:
            if l in self.abs_name_map and ctrlname('eye_master.L') in self.abs_name_map:
                eb[ rbn( l ) ].use_connect = False
                eb[ rbn( l ) ].parent = eb[ rbn( ctrlname('eye_master.L') ) ]

        for r in right:
            if r in self.abs_name_map and ctrlname('eye_master.R') in self.abs_name_map:
                eb[ rbn( r ) ].use_connect = False
                eb[ rbn( r ) ].parent = eb[ rbn( ctrlname('eye_master.R') ) ]

        ## turbo: nose to mch jaw.004
        if mchname('jaw_master.004') in self.abs_name_map and 'nose' in all_bones['ctrls'] and len(all_bones['ctrls']['nose']) > 0:
            nosetop = all_bones['ctrls']['nose'].pop()
            eb[ rbn( nosetop ) ].use_connect = False
            eb[ rbn( nosetop ) ].parent = eb[ rbn( mchname('jaw_master.004') ) ]

        ## Parenting the tweak bones
        
        def interctrlnames(name):
            if name in self.tail_mid_map:
                return [ctrlname(name + '.%03d' % i) for i in range(1, self.tail_mid_map[name][2])]
            return []

        midctrlname = self.midctrlname
        tailctrlname = self.tailctrlname

        # Jaw children (values) groups and their parents (keys)
        groups = {
            ctrlname('jaw_master'): [
                ctrlname('jaw'),
                ctrlname('jaw.L'),
                ctrlname('jaw.R'),
                ctrlname('jaw.L.001'),
                ctrlname('jaw.R.001'),
                ctrlname('chin.L'),
                ctrlname('chin.R'),
                ctrlname('chin'),
                mchname('chin'),
                tailctrlname('tongue')
            ],
            mchname('jaw_master'): [ ctrlname('lip.B') ],
            mchname('jaw_master.001'): interctrlnames('lip.B.L') + interctrlnames('lip.B.R'),
            mchname('jaw_master.002'): [ ctrlname('lips.L'), ctrlname('lips.R') ] + interctrlnames('cheek.B.L') + interctrlnames('cheek.B.R'),
            mchname('jaw_master.003'): [ ctrlname('lip.T') ] + interctrlnames('lip.T.L') + interctrlnames('lip.T.R'),
            mchname('jaw_master.004'): interctrlnames('cheek.T.L') + interctrlnames('cheek.T.R'),
            ctrlname('nose_master'): interctrlnames('nose') + [ tailctrlname('nose') ] + interctrlnames('nose.L') + interctrlnames('nose.R'),
        }

        for parent, bones in groups.items():
            for bone in bones:
                if bone in self.abs_name_map and parent in self.abs_name_map:
                    eb[ rbn( bone ) ].parent = eb[ rbn( parent ) ]

        # if MCH-target_jaw has no parent, parent to jaw_master.
        if mchname('target_jaw') in self.abs_name_map and ctrlname('jaw_master') in self.abs_name_map and eb[ rbn( mchname('target_jaw') ) ].parent is None:
            eb[ rbn( mchname('target_jaw') ) ].parent = eb[ rbn( ctrlname('jaw_master') ) ]

        # if chin_parent is exist, parent chin to chin_parent
        if 'chin_parent' in all_bones['mch']:
            if ctrlname('chin') in self.abs_name_map:
                eb[ rbn( ctrlname('chin') ) ].use_connect = False
                eb[ rbn( ctrlname('chin') ) ].parent = eb[ rbn( all_bones['mch']['chin_parent'][0] ) ]
            if ctrlname('chin.L') in self.abs_name_map:
                eb[ rbn( ctrlname('chin.L') ) ].parent = eb[ rbn( all_bones['mch']['chin_parent'][0] ) ]
            if ctrlname('chin.R') in self.abs_name_map:
                eb[ rbn( ctrlname('chin.R') ) ].parent = eb[ rbn( all_bones['mch']['chin_parent'][0] ) ]

        # Remaining arbitrary relatioships for tweak bone parenting
        if ctrlname('chin.001') in self.abs_name_map and ctrlname('chin') in self.abs_name_map:
            eb[ rbn( ctrlname('chin.001') ) ].parent = eb[ rbn( ctrlname('chin') ) ]
        if tailctrlname('chin') in self.abs_name_map and ctrlname('lip.B') in self.abs_name_map:
            eb[ rbn( tailctrlname('chin') ) ].parent = eb[ rbn( ctrlname('lip.B') ) ]
        if ctrlname('nose.001') in self.abs_name_map and ctrlname('nose.002') in self.abs_name_map:
            eb[ rbn( ctrlname('nose.001') ) ].parent = eb[ rbn( ctrlname('nose.002') ) ]
        if ctrlname('nose.003') in self.abs_name_map and ctrlname('nose.002') in self.abs_name_map:
            eb[ rbn( ctrlname('nose.003') ) ].parent = eb[ rbn( ctrlname('nose.002') ) ]
        if tailctrlname('nose') in self.abs_name_map and ctrlname('lip.T') in self.abs_name_map:
            eb[ rbn( tailctrlname('nose') ) ].parent = eb[ rbn( ctrlname('lip.T') ) ]
        if ctrlname('tongue') in self.abs_name_map and ctrlname('tongue_master') in self.abs_name_map:
            eb[ rbn( ctrlname('tongue') ) ].parent = eb[ rbn( ctrlname('tongue_master') ) ]
        if 'tongue' in self.tail_mid_map:
            for i in range(self.tail_mid_map['tongue'][2]):
                b = 'tongue.%03d' % i
                if ctrlname(b) in self.abs_name_map and b in self.abs_name_map:
                    eb[ rbn( ctrlname(b) ) ].parent = eb[ rbn( mchname(b) ) ]
        if 'ear.L' in self.tail_mid_map:
            for bone in [ctrlname('ear.L.%03d' % i) for i in range(2, self.tail_mid_map['ear.L'][2])]:
                eb[ rbn( bone )].parent = eb[ rbn( ctrlname('ear.L') ) ]
        if 'ear.R' in self.tail_mid_map:
            for bone in [ctrlname('ear.R.%03d' % i) for i in range(2, self.tail_mid_map['ear.R'][2])]:
                eb[ rbn( bone )].parent = eb[ rbn( ctrlname('ear.R') ) ]

        # Parent all rest of mch-target bones to the face as default
        for bone in mchts:
            mcht_eb = eb[ rbn( bone ) ]
            if mcht_eb.parent is None:
                mcht_eb.parent = eb[ rbn(face_name) ]

        # Parent all org bones to the face
        for bone in self.org_bones:
            if bone != face_name:
                eb[ rbn(bone) ].use_connect = False
                eb[ rbn(bone) ].parent = eb[ rbn(face_name) ]


    def make_constraits( self, constraint_type, bone, subtarget, influence = 1 ):
        rbn = self.rbn
        pb = self.obj.pose.bones
        
        if not (bone in self.abs_name_map and subtarget in self.abs_name_map):
            return

        owner_pb = pb[rbn(bone)]

        if constraint_type == 'def_tweak':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

            const = owner_pb.constraints.new( 'STRETCH_TO' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

        elif constraint_type == 'mch_target':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target       = self.obj
            const.subtarget    = rbn(subtarget)
            const.influence    = influence
            const.target_space = 'WORLD'
            const.owner_space  = 'WORLD'
        
        elif constraint_type == 'def_lids':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.head_tail = 1.0

            const = owner_pb.constraints.new( 'STRETCH_TO' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.head_tail = 1.0

        elif constraint_type == 'mch_lids':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

            const = owner_pb.constraints.new( 'STRETCH_TO' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
        
        elif constraint_type == 'mch_eyes':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

        elif constraint_type == 'mch_eyes_lids_follow':

            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.head_tail = 1.0

        elif constraint_type == 'mch_eyes_parent':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

        elif constraint_type == 'mch_jaw_master':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.influence = influence
        
        elif constraint_type == 'mch_tongue_parent':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

        elif constraint_type == 'mch_chin_parent':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)

        elif constraint_type == 'teeth':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.influence = influence

        elif constraint_type == 'tweak_copyloc':

            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target       = self.obj
            const.subtarget    = rbn(subtarget)
            const.influence    = influence
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'

        elif constraint_type == 'tweak_copy_rot_scl':

            const = owner_pb.constraints.new( 'COPY_ROTATION' )
            const.target       = self.obj
            const.subtarget    = rbn(subtarget)
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'

            const = owner_pb.constraints.new( 'COPY_SCALE' )
            const.target       = self.obj
            const.subtarget    = rbn(subtarget)
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'

        elif constraint_type == 'tweak_copyloc_inv':

            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target       = self.obj
            const.subtarget    = rbn(subtarget)
            const.influence    = influence
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'
            const.use_offset   = True
            const.invert_x     = True
            const.invert_y     = True
            const.invert_z     = True

        elif constraint_type == 'mch_tongue_copy_trans':

            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = rbn(subtarget)
            const.influence = influence


    def constraints( self, all_bones, mchts ):
        ## Def bone constraints
        def mid_mch_target(name):
            if name in self.tail_mid_map:
                return mch_target(self.tail_mid_map[name][1])
        def tail_mch_target(name):
            if name in self.tail_mid_map:
                return mch_target(self.tail_mid_map[name][0])
        tailctrlname = self.tailctrlname
        midctrlname = self.midctrlname

        def_specials = {
            # 'bone'                     : 'target'
            mch_target('jaw')            : mchname('chin'),
            mch_target('chin.L')         : ctrlname('lips.L'),
            tail_mch_target('jaw.L')     : ctrlname('chin.L'),
            mch_target('chin.R')         : ctrlname('lips.R'),
            tail_mch_target('jaw.R')     : ctrlname('chin.R'),
            tail_mch_target('ear.L')     : tailctrlname('ear.L') if 'ear.L' in self.tail_mid_map and self.tail_mid_map['ear.L'][2] > 1 else None,
            tail_mch_target('ear.L')     : ctrlname('ear.L') if 'ear.L' in self.tail_mid_map and self.tail_mid_map['ear.L'][2] > 2 else None,
            tail_mch_target('ear.R')     : tailctrlname('ear.R') if 'ear.R' in self.tail_mid_map and self.tail_mid_map['ear.R'][2] > 1 else None,
            tail_mch_target('ear.R')     : ctrlname('ear.R') if 'ear.R' in self.tail_mid_map and self.tail_mid_map['ear.R'][2] > 2 else None,
            tail_mch_target('cheek.B.L') : ctrlname('brow.T.L'),
            tail_mch_target('cheek.B.R') : ctrlname('brow.T.R'),
            tail_mch_target('cheek.T.L') : ctrlname('nose.L'),
            tail_mch_target('cheek.T.R') : ctrlname('nose.R'),
            tail_mch_target('nose.L')    : midctrlname('nose'),
            tail_mch_target('nose.R')    : midctrlname('nose'),
            mch_target('temple.L')       : ctrlname('jaw.L'),
            mch_target('temple.R')       : ctrlname('jaw.R'),
            tail_mch_target('brow.T.L')  : ctrlname('nose'),
            tail_mch_target('brow.T.R')  : ctrlname('nose'),
            tail_mch_target('lip.B.L')   : ctrlname('lips.L'),
            tail_mch_target('lip.B.R')   : ctrlname('lips.R'),
            tail_mch_target('lip.T.L')   : ctrlname('lips.L'),
            tail_mch_target('lip.T.R')   : ctrlname('lips.R'),
        }

        pattern = re.compile(r'^'+mch_target(r'(\w+\.?\w?\.?\w?)(\.?)(\d*?)(\d?)$'))

        for bone in [ bone for bone in mchts if 'lid.' not in bone ]:
            if bone in def_specials.keys():
                self.make_constraits('def_tweak', bone, def_specials[bone] )
            else:
                matches = pattern.match( bone ).groups()
                if len( matches ) > 1 and matches[-1]:
                    num = int( matches[-1] ) + 1
                    str_list = list( matches )[:-1] + [ str( num ) ]
                    tweak = "".join( str_list )
                else:
                    tweak = "".join( matches ) + ".001"
                self.make_constraits('def_tweak', bone, ctrlname(tweak) )

        def_lids = sorted( [ bone for bone in mchts if 'lid' in bone ] )
        mch_lids = sorted( [ bone for bone in all_bones['mch']['lids'] ] )

        def_lidsL, def_lidsR = self.symmetrical_split( def_lids )
        mch_lidsL, mch_lidsR = self.symmetrical_split( mch_lids )

        # Take the last mch_lid bone and place it at the end
        if len(mch_lidsL) > 1:
            mch_lidsL = mch_lidsL[1:] + [ mch_lidsL[0] ]
        if len(mch_lidsR) > 1:
            mch_lidsR = mch_lidsR[1:] + [ mch_lidsR[0] ]

        for boneL, boneR, mchL, mchR in zip( def_lidsL, def_lidsR, mch_lidsL, mch_lidsR ):
            self.make_constraits('def_lids', boneL, mchL )
            self.make_constraits('def_lids', boneR, mchR )

        ## MCH constraints

        # mch lids constraints
        for bone in all_bones['mch']['lids']:
            tweak = ctrlname(basename(bone))
            self.make_constraits('mch_lids', bone, tweak )

        # mch eyes constraints
        for bone in [ mchname('eye.L'), mchname('eye.R') ]:
            ctrl = ctrlname(basename(bone))  # remove "MCH-" from bone name
            self.make_constraits('mch_eyes', bone, ctrl )

        for bone in [ mchname('eye.L.001'), mchname('eye.R.001') ]:
            target = bone[:-4] # remove number from the end of the name
            self.make_constraits('mch_eyes_lids_follow', bone, target ) 

        # mch eyes parent constraints
        self.make_constraits('mch_eyes_parent', mchname('eyes_parent'), 'face' )

        ## Jaw constraints

        # jaw master mch bones
        self.make_constraits( 'mch_jaw_master', mchname('mouth_lock'),     ctrlname('jaw_master'), 0.20  )
        self.make_constraits( 'mch_jaw_master', mchname('jaw_master'),     ctrlname('jaw_master'), 1.00  )
        self.make_constraits( 'mch_jaw_master', mchname('jaw_master.001'), ctrlname('jaw_master'), 0.75  )
        self.make_constraits( 'mch_jaw_master', mchname('jaw_master.002'), ctrlname('jaw_master'), 0.35  )
        self.make_constraits( 'mch_jaw_master', mchname('jaw_master.003'), ctrlname('jaw_master'), 0.10  )
        self.make_constraits( 'mch_jaw_master', mchname('jaw_master.004'), ctrlname('jaw_master'), 0.025 )

        if 'jaw' in all_bones['mch']:
            for bone in all_bones['mch']['jaw'][1:-1]:
                self.make_constraits( 'mch_jaw_master', bone, mchname('mouth_lock') )

        ## Tweak bones constraints

        # copy location constraints for tweak bones of both sides
        tweak_copyloc = {
            midctrlname('brow.B.L')   : [ [ midctrlname('brow.T.L'),                       ], [ 0.25      ] ],
            midctrlname('brow.B.R')   : [ [ midctrlname('brow.T.R'),                       ], [ 0.25      ] ],
            midctrlname('lid.T.L')    : [ [ mchname('eye.L.001'),                          ], [ 0.5       ] ],
            midctrlname('lid.T.R')    : [ [ mchname('eye.R.001'),                          ], [ 0.5       ] ],
            midctrlname('lid.B.L')    : [ [ mchname('eye.L.001'), midctrlname('cheek.T.L') ], [ 0.5, 0.1  ] ],
            midctrlname('lid.B.R')    : [ [ mchname('eye.R.001'), midctrlname('cheek.T.R') ], [ 0.5, 0.1  ] ],
            midctrlname('cheek.T.L')  : [ [ midctrlname('cheek.B.L'),                      ], [ 0.5       ] ],
            midctrlname('cheek.T.R')  : [ [ midctrlname('cheek.B.R'),                      ], [ 0.5       ] ],
            tailctrlname('nose.L')    : [ [ tailctrlname('lip.T.L'),                       ], [ 0.2       ] ],
            tailctrlname('nose.R')    : [ [ tailctrlname('lip.T.R'),                       ], [ 0.2       ] ],
            tailctrlname('cheek.B.L') : [ [ ctrlname('lips.L'),                            ], [ 0.5       ] ],
            tailctrlname('cheek.B.R') : [ [ ctrlname('lips.R'),                            ], [ 0.5       ] ],
            midctrlname('lip.T.L')    : [ [ ctrlname('lips.L'), ctrlname('lip.T')          ], [ 0.25, 0.5 ] ],
            midctrlname('lip.T.R')    : [ [ ctrlname('lips.R'), ctrlname('lip.T')          ], [ 0.25, 0.5 ] ],
            midctrlname('lip.B.L')    : [ [ ctrlname('lips.L'), ctrlname('lip.B')          ], [ 0.25, 0.5 ] ],
            midctrlname('lip.B.R')    : [ [ ctrlname('lips.R'), ctrlname('lip.B')          ], [ 0.25, 0.5 ] ],
        }
        # top to tail
        for name in ('nose.L', 'nose.R'):
            if name in self.tail_mid_map and self.tail_mid_map[name][2] > 1:
                l = self.tail_mid_map[name][2]
                for i in range(1, l):
                    tweak_copyloc[ ctrlname(name + '.%03d' % i) ] = [ [ ctrlname(name) ], [ 0.25 / i ] ]
        # mid to other
        for name in (
            'brow.T.L', 'brow.T.R', 'brow.B.L', 'brow.B.R',
            'lid.T.L', 'lid.T.R', 'lid.B.L', 'lid.B.R',
            'lip.T.L', 'lip.T.R', 'lip.B.L', 'lip.B.R',
            'ear.L', 'ear.R'
        ):
            if name in self.tail_mid_map and self.tail_mid_map[name][2] > 2:
                l = self.tail_mid_map[name][2]
                for i in filter(lambda x: x != int(l / 2), range(1, l)):
                    tweak_copyloc[ ctrlname(name + '.%03d' % i) ] = [ [ midctrlname(name) ], [ (l / 2 - i) / (l / 2) if i < l / 2 else (l - i) / (l - l / 2) ] ]

        for k, v in tweak_copyloc.items():
            if k:
                for target, influence in zip( v[0], v[1] ):
                    if target:
                        self.make_constraits( 'tweak_copyloc', k, target, influence )

        # copy rotation & scale constraints for tweak bones of both sides
        tweak_copy_rot_scl = {
            midctrlname('lip.T.L'): ctrlname('lip.T'),
            midctrlname('lip.T.R'): ctrlname('lip.T'),
            midctrlname('lip.B.L'): ctrlname('lip.B'),
            midctrlname('lip.B.R'): ctrlname('lip.B'),
        }

        for k, v in tweak_copy_rot_scl.items():
            self.make_constraits( 'tweak_copy_rot_scl', k, v )

        # inverted tweak bones constraints
        tweak_nose = [
            [ ctrlname('nose.001'),     ctrlname('nose.002'), 0.35 ],
            [ ctrlname('nose.003'),     ctrlname('nose.002'), 0.5  ],
            [ tailctrlname('nose'),     ctrlname('lip.T'),    0.5  ],
            [ tailctrlname('chin.002'), ctrlname('lip.B'),    0.5  ],
        ]

        for owner, target, influence in tweak_nose:
            self.make_constraits( 'tweak_copyloc_inv', owner, target, influence )
        
        # MCH tongue constraints
        if 'tongue' in all_bones['mch']:
            divider = len( all_bones['mch']['tongue'] ) + 1
            factor  = len( all_bones['mch']['tongue'] )

            for owner in all_bones['mch']['tongue']:
                self.make_constraits( 'mch_tongue_copy_trans', owner, ctrlname('tongue_master'), ( 1 / divider ) * factor )
                factor -= 1
        
        # MCH tongue parent constraints
        if 'tongue_parent' in all_bones['mch']:
            self.make_constraits('mch_tongue_parent', mchname('tongue_parent'), mchname('jaw_master') )
        
        # MCH chin parent constraints
        if 'chin_parent' in all_bones['mch']:
            self.make_constraits('mch_chin_parent', mchname('chin_parent'), mchname('jaw_master') )

        # orginal bones constraints
        for bone in self.org_bones:
            self.make_constraits( 'mch_target', bone, mch_target( bone ) )


    def drivers_and_props( self, all_bones ):
        rbn = self.rbn
        pb = self.obj.pose.bones

        # Mouse Lock
        ctrl  = all_bones['ctrls']['jaw'][0] if 'jaw' in all_bones['ctrls'] else None
        if ctrl and 'jaw' in all_bones['mch']:
            ctrl_bone = rbn(ctrl)
            prop_name = 'Mouth Lock'
            pb[ ctrl_bone ][ prop_name ] = 0.0
            prop = rna_idprop_ui_prop_get( pb[ ctrl_bone ], prop_name )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = "Mouth bones don't move if jaw moves"
            mch_jaws = all_bones['mch']['jaw'][1:-1]

            # Jaw drivers
            for bone in mch_jaws:
                drv = pb[ rbn(bone) ].constraints[1].driver_add("influence").driver
                drv.type='SUM'

                var = drv.variables.new()
                var.name = 'mouth_lock'
                var.type = "SINGLE_PROP"
                var.targets[0].id = self.obj
                var.targets[0].data_path = pb[ ctrl_bone ].path_from_id() + '['+ '"' + prop_name + '"' + ']'

        # Eyes Follow
        ctrl = all_bones['ctrls']['eyes'][2] if 'eyes' in all_bones['ctrls'] else None
        if ctrl and 'eyes_parent' in all_bones['mch']:
            ctrl_bone = rbn(ctrl)
            prop_name = 'Eyes Follow'
            pb[ ctrl_bone ][ prop_name ] = 1.0
            prop = rna_idprop_ui_prop_get( pb[ ctrl_bone ], prop_name )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'Switch eyes follow to face'

            # Eyes driver
            mch_eyes_parent = all_bones['mch']['eyes_parent'][0]

            drv = pb[ rbn(mch_eyes_parent) ].constraints[0].driver_add("influence").driver
            drv.type='SUM'

            var = drv.variables.new()
            var.name = 'eyes_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[ ctrl_bone ].path_from_id() + '['+ '"' + prop_name + '"' + ']'

        # Tongue Follow
        ctrl = all_bones['ctrls']['tongue'][0] if 'tongue' in all_bones['ctrls'] else None
        if ctrl and 'tongue_parent' in all_bones['mch']:
            ctrl_bone = rbn(ctrl)
            prop_name = 'Tongue Follow'
            pb[ ctrl_bone ][ 'Tongue Follow' ] = 1.0
            prop = rna_idprop_ui_prop_get( pb[ ctrl_bone ], 'Tongue Follow' )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'Switch tongue follow to jaw or face'

            # Tongue driver
            mch_tongue_parent = all_bones['mch']['tongue_parent'][0]

            drv = pb[ rbn(mch_tongue_parent) ].constraints[0].driver_add("influence").driver
            drv.type='SUM'

            var = drv.variables.new()
            var.name = 'tongue_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[ ctrl_bone ].path_from_id() + '['+ '"' + prop_name + '"' + ']'

        # Chin Follow
        ctrl = ctrlname('chin') if ctrlname('chin') in all_bones['tweaks']['all'] else None
        if ctrl and 'chin_parent' in all_bones['mch']:
            ctrl_bone = rbn(ctrl)
            prop_name = 'Chin Follow'
            pb[ ctrl_bone ][ 'Chin Follow' ] = 1.0
            prop = rna_idprop_ui_prop_get( pb[ ctrl_bone ], 'Chin Follow' )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = 'Switch chin follow to jaw or face'

            # Tongue driver
            mch_chin_parent = all_bones['mch']['chin_parent'][0]

            drv = pb[ rbn(mch_chin_parent) ].constraints[0].driver_add("influence").driver
            drv.type='SUM'

            var = drv.variables.new()
            var.name = 'chin_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[ ctrl_bone ].path_from_id() + '['+ '"' + prop_name + '"' + ']'


    def create_bones(self):
        rbn = self.rbn
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        face_name = 'face'

        # Clear parents for org lid bones
        for bone in self.org_bones:
            if bone != face_name and 'lid.' in bone:
                eb[rbn(bone)].use_connect = False
                eb[rbn(bone)].parent      = None
        
        mch_targets = self.create_mch_targets()

        all_bones = {}

        ctrls, tweak_unique = self.all_controls()
        mchs = self.create_mch(
            ctrls['ctrls']['jaw'][0] if 'jaw' in ctrls['ctrls'] else None,
            ctrls['ctrls']['tongue'][0] if 'tongue' in ctrls['ctrls'] else None,
            ctrlname('chin') if ctrlname('chin') in ctrls['tweaks']['all'] else None
        )

        return {
            'ctrls' : ctrls['ctrls'],
            'tweaks': ctrls['tweaks'],
            'mch'   : mchs
        }, tweak_unique, mch_targets


    def generate(self, context):

        all_bones, tweak_unique, mchts = self.create_bones()
        self.parent_bones( all_bones, tweak_unique, mchts )

        self.all_bones = all_bones
        self.mchts = mchts

        # Create UI
        all_controls =  [ bone for bone in [ bgroup for bgroup in [ all_bones['ctrls'][group]  for group in list( all_bones['ctrls' ].keys() ) ] ] ]
        all_controls += [ bone for bone in [ bgroup for bgroup in [ all_bones['tweaks'][group] for group in list( all_bones['tweaks'].keys() ) ] ] ]

        all_ctrls = []
        for group in all_controls:
            for bone in group:
                all_ctrls.append( bone )

        controls_string = ", ".join(["'" + x + "'" for x in all_ctrls])
        jaw_ctrl = all_bones['ctrls']['jaw'][0] if 'jaw' in all_bones['ctrls'] else None
        eyes_ctrl = all_bones['ctrls']['eyes'][2] if 'eyes' in all_bones['ctrls'] else None
        tongue_ctrl = all_bones['ctrls']['tongue'][0] if 'tongue' in all_bones['ctrls'] else None
        chin_ctrl = self.rbn(ctrlname('chin')) if ctrlname('chin') in all_bones['tweaks']['all'] else None

        return """
# Face properties
controls   = [%s]
if is_selected(controls):
""" % controls_string + \
("""    layout.prop(pose_bones['%s'],  '["Mouth Lock"]', text='Mouth Lock (%s)', slider=True)
""" % (jaw_ctrl, jaw_ctrl) if jaw_ctrl else "") + \
("""    layout.prop(pose_bones['%s'],  '["Eyes Follow"]', text='Eyes Follow (%s)', slider=True)
""" % (eyes_ctrl, eyes_ctrl) if eyes_ctrl else "") + \
("""    layout.prop(pose_bones['%s'], '["Tongue Follow"]', text='Tongue Follow (%s)', slider=True)
""" % (tongue_ctrl, tongue_ctrl) if tongue_ctrl else "") + \
("""    layout.prop(pose_bones['%s'], '["Chin Follow"]', text='Chin Follow (%s)', slider=True)
""" % (chin_ctrl, chin_ctrl) if chin_ctrl else "")


    def postprocess(self, context):
        self.constraints( self.all_bones, self.mchts )
        self.drivers_and_props( self.all_bones )
        self.create_ctrl_widget(self.all_bones['ctrls'])
        self.create_tweak_widget(self.all_bones['tweaks']['all'])


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """

    #Setting up extra layers for the tweak bones
    params.primary_layers_extra = bpy.props.BoolProperty(
        name        = "primary_layers_extra",
        default     = True,
        description = ""
    )
    params.primary_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the 1st tweak controls to be on",
        default     = tuple( [ i == 1 for i in range(0, 32) ] )
    )
    params.secondary_layers_extra = bpy.props.BoolProperty(
        name        = "secondary_layers_extra",
        default     = True,
        description = ""
    )
    params.secondary_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the 2nd tweak controls to be on",
        default     = tuple( [ i == 2 for i in range(0, 32) ] )
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""
    layers = ["primary_layers", "secondary_layers"]

    for layer in layers:
        r = layout.row()
        r.prop( params, layer + "_extra" )
        r.active = getattr( params, layer + "_extra" )

        col = r.column(align=True)
        row = col.row(align=True)
        for i in range(8):
            row.prop(params, layer, index=i, toggle=True, text="")

        row = col.row(align=True)
        for i in range(16,24):
            row.prop(params, layer, index=i, toggle=True, text="")

        col = r.column(align=True)
        row = col.row(align=True)

        for i in range(8,16):
            row.prop(params, layer, index=i, toggle=True, text="")

        row = col.row(align=True)
        for i in range(24,32):
            row.prop(params, layer, index=i, toggle=True, text="")


def create_square_widget(rig, bone_name, size=1.0, bone_transform_name=None):
    obj = create_widget(rig, bone_name, bone_transform_name)
    if obj is not None:
        verts = [
            (  0.5 * size, 0 * size,  0.5 * size ),
            ( -0.5 * size, 0 * size,  0.5 * size ),
            (  0.5 * size, 0 * size, -0.5 * size ),
            ( -0.5 * size, 0 * size, -0.5 * size ),
        ]

        edges = [(0, 1), (2, 3), (0, 2), (3, 1) ]
        faces = []

        mesh = obj.data
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        return obj
    else:
        return None


def create_sample(obj):
    # generated by gamerig.utils.write_metarig

    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('head')
    bone.head[:] = 0.0035, 0.0015, 0.0436
    bone.tail[:] = 0.0035, 0.0015, 0.2133
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bones['head'] = bone.name
    bone = arm.edit_bones.new('nose')
    bone.head[:] = 0.0035, -0.0905, 0.1293
    bone.tail[:] = 0.0035, -0.0884, 0.1143
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['nose'] = bone.name
    bone = arm.edit_bones.new('lip.T.L')
    bone.head[:] = 0.0035, -0.0974, 0.0588
    bone.tail[:] = 0.0189, -0.0931, 0.0592
    bone.roll = -1.5683
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lip.T.L'] = bone.name
    bone = arm.edit_bones.new('lip.B.L')
    bone.head[:] = 0.0035, -0.0940, 0.0459
    bone.tail[:] = 0.0181, -0.0875, 0.0499
    bone.roll = -1.4321
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lip.B.L'] = bone.name
    bone = arm.edit_bones.new('jaw')
    bone.head[:] = 0.0035, -0.0463, 0.0159
    bone.tail[:] = 0.0035, -0.0773, 0.0057
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['jaw'] = bone.name
    bone = arm.edit_bones.new('ear.L')
    bone.head[:] = 0.0762, -0.0051, 0.0936
    bone.tail[:] = 0.0817, -0.0040, 0.1281
    bone.roll = -0.0484
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['ear.L'] = bone.name
    bone = arm.edit_bones.new('lip.T.R')
    bone.head[:] = 0.0035, -0.0974, 0.0588
    bone.tail[:] = -0.0119, -0.0931, 0.0592
    bone.roll = 1.5683
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lip.T.R'] = bone.name
    bone = arm.edit_bones.new('lip.B.R')
    bone.head[:] = 0.0035, -0.0940, 0.0459
    bone.tail[:] = -0.0111, -0.0875, 0.0499
    bone.roll = 1.4321
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lip.B.R'] = bone.name
    bone = arm.edit_bones.new('brow.B.L')
    bone.head[:] = 0.0661, -0.0600, 0.1304
    bone.tail[:] = 0.0592, -0.0688, 0.1349
    bone.roll = 2.2128
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['brow.B.L'] = bone.name
    bone = arm.edit_bones.new('lid.T.L')
    bone.head[:] = 0.0643, -0.0585, 0.1226
    bone.tail[:] = 0.0571, -0.0694, 0.1264
    bone.roll = 1.8844
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lid.T.L'] = bone.name
    bone = arm.edit_bones.new('brow.B.R')
    bone.head[:] = -0.0591, -0.0600, 0.1304
    bone.tail[:] = -0.0522, -0.0688, 0.1349
    bone.roll = -2.2128
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['brow.B.R'] = bone.name
    bone = arm.edit_bones.new('lid.T.R')
    bone.head[:] = -0.0573, -0.0585, 0.1226
    bone.tail[:] = -0.0501, -0.0694, 0.1264
    bone.roll = -1.8844
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['lid.T.R'] = bone.name
    bone = arm.edit_bones.new('temple.L')
    bone.head[:] = 0.0726, -0.0279, 0.1682
    bone.tail[:] = 0.0732, -0.0290, 0.0951
    bone.roll = -0.0303
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['temple.L'] = bone.name
    bone = arm.edit_bones.new('temple.R')
    bone.head[:] = -0.0656, -0.0279, 0.1682
    bone.tail[:] = -0.0662, -0.0290, 0.0951
    bone.roll = 0.0303
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['temple.R'] = bone.name
    bone = arm.edit_bones.new('eye.L')
    bone.head[:] = 0.0443, -0.0577, 0.1221
    bone.tail[:] = 0.0443, -0.0769, 0.1221
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['eye.L'] = bone.name
    bone = arm.edit_bones.new('eye.R')
    bone.head[:] = -0.0373, -0.0577, 0.1221
    bone.tail[:] = -0.0373, -0.0769, 0.1221
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['eye.R'] = bone.name
    bone = arm.edit_bones.new('cheek.T.L')
    bone.head[:] = 0.0706, -0.0365, 0.1165
    bone.tail[:] = 0.0482, -0.0752, 0.0886
    bone.roll = -0.0096
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['cheek.T.L'] = bone.name
    bone = arm.edit_bones.new('cheek.T.R')
    bone.head[:] = -0.0636, -0.0365, 0.1165
    bone.tail[:] = -0.0412, -0.0752, 0.0886
    bone.roll = 0.0096
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['cheek.T.R'] = bone.name
    bone = arm.edit_bones.new('tongue')
    bone.head[:] = 0.0035, -0.0878, 0.0434
    bone.tail[:] = 0.0035, -0.0678, 0.0478
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['tongue'] = bone.name
    bone = arm.edit_bones.new('ear.R')
    bone.head[:] = -0.0692, -0.0051, 0.0936
    bone.tail[:] = -0.0747, -0.0040, 0.1281
    bone.roll = 0.0484
    bone.use_connect = False
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['head']]
    bones['ear.R'] = bone.name
    bone = arm.edit_bones.new('nose.001')
    bone.head[:] = 0.0035, -0.0884, 0.1143
    bone.tail[:] = 0.0035, -0.1176, 0.0833
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['nose']]
    bones['nose.001'] = bone.name
    bone = arm.edit_bones.new('lip.T.L.001')
    bone.head[:] = 0.0189, -0.0931, 0.0592
    bone.tail[:] = 0.0313, -0.0803, 0.0535
    bone.roll = -1.0989
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lip.T.L']]
    bones['lip.T.L.001'] = bone.name
    bone = arm.edit_bones.new('lip.B.L.001')
    bone.head[:] = 0.0181, -0.0875, 0.0499
    bone.tail[:] = 0.0313, -0.0803, 0.0535
    bone.roll = -1.3635
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lip.B.L']]
    bones['lip.B.L.001'] = bone.name
    bone = arm.edit_bones.new('chin')
    bone.head[:] = 0.0035, -0.0773, 0.0057
    bone.tail[:] = 0.0035, -0.0914, 0.0209
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['jaw']]
    bones['chin'] = bone.name
    bone = arm.edit_bones.new('ear.L.001')
    bone.head[:] = 0.0817, -0.0040, 0.1281
    bone.tail[:] = 0.0984, 0.0173, 0.1326
    bone.roll = -1.5279
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.L']]
    bones['ear.L.001'] = bone.name
    bone = arm.edit_bones.new('lip.T.R.001')
    bone.head[:] = -0.0119, -0.0931, 0.0592
    bone.tail[:] = -0.0243, -0.0803, 0.0535
    bone.roll = 1.0989
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lip.T.R']]
    bones['lip.T.R.001'] = bone.name
    bone = arm.edit_bones.new('lip.B.R.001')
    bone.head[:] = -0.0111, -0.0875, 0.0499
    bone.tail[:] = -0.0243, -0.0803, 0.0535
    bone.roll = 1.3635
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lip.B.R']]
    bones['lip.B.R.001'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.001')
    bone.head[:] = 0.0592, -0.0688, 0.1349
    bone.tail[:] = 0.0491, -0.0750, 0.1368
    bone.roll = 1.3466
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.L']]
    bones['brow.B.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.001')
    bone.head[:] = 0.0571, -0.0694, 0.1264
    bone.tail[:] = 0.0470, -0.0757, 0.1285
    bone.roll = 1.4034
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.L']]
    bones['lid.T.L.001'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.001')
    bone.head[:] = -0.0522, -0.0688, 0.1349
    bone.tail[:] = -0.0421, -0.0750, 0.1368
    bone.roll = -1.3466
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.R']]
    bones['brow.B.R.001'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.001')
    bone.head[:] = -0.0501, -0.0694, 0.1264
    bone.tail[:] = -0.0400, -0.0757, 0.1285
    bone.roll = -1.4034
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.R']]
    bones['lid.T.R.001'] = bone.name
    bone = arm.edit_bones.new('jaw.L')
    bone.head[:] = 0.0732, -0.0290, 0.0951
    bone.tail[:] = 0.0639, -0.0352, 0.0457
    bone.roll = -0.0885
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['temple.L']]
    bones['jaw.L'] = bone.name
    bone = arm.edit_bones.new('jaw.R')
    bone.head[:] = -0.0662, -0.0290, 0.0951
    bone.tail[:] = -0.0569, -0.0352, 0.0457
    bone.roll = 0.0885
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['temple.R']]
    bones['jaw.R'] = bone.name
    bone = arm.edit_bones.new('cheek.T.L.001')
    bone.head[:] = 0.0482, -0.0752, 0.0886
    bone.tail[:] = 0.0184, -0.0767, 0.1127
    bone.roll = 2.2836
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.T.L']]
    bones['cheek.T.L.001'] = bone.name
    bone = arm.edit_bones.new('cheek.T.R.001')
    bone.head[:] = -0.0412, -0.0752, 0.0886
    bone.tail[:] = -0.0114, -0.0767, 0.1127
    bone.roll = -2.2836
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.T.R']]
    bones['cheek.T.R.001'] = bone.name
    bone = arm.edit_bones.new('tongue.001')
    bone.head[:] = 0.0035, -0.0678, 0.0478
    bone.tail[:] = 0.0044, -0.0502, 0.0473
    bone.roll = -0.0059
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['tongue']]
    bones['tongue.001'] = bone.name
    bone = arm.edit_bones.new('ear.R.001')
    bone.head[:] = -0.0747, -0.0040, 0.1281
    bone.tail[:] = -0.0914, 0.0173, 0.1326
    bone.roll = 1.5279
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.R']]
    bones['ear.R.001'] = bone.name
    bone = arm.edit_bones.new('nose.002')
    bone.head[:] = 0.0035, -0.1176, 0.0833
    bone.tail[:] = 0.0035, -0.0983, 0.0730
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['nose.001']]
    bones['nose.002'] = bone.name
    bone = arm.edit_bones.new('chin.001')
    bone.head[:] = 0.0035, -0.0914, 0.0209
    bone.tail[:] = 0.0035, -0.0910, 0.0405
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['chin']]
    bones['chin.001'] = bone.name
    bone = arm.edit_bones.new('ear.L.002')
    bone.head[:] = 0.0984, 0.0173, 0.1326
    bone.tail[:] = 0.0861, 0.0043, 0.0876
    bone.roll = -0.6486
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.L.001']]
    bones['ear.L.002'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.002')
    bone.head[:] = 0.0491, -0.0750, 0.1368
    bone.tail[:] = 0.0342, -0.0743, 0.1342
    bone.roll = 1.2633
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.L.001']]
    bones['brow.B.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.002')
    bone.head[:] = 0.0470, -0.0757, 0.1285
    bone.tail[:] = 0.0338, -0.0767, 0.1258
    bone.roll = 1.1877
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.L.001']]
    bones['lid.T.L.002'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.002')
    bone.head[:] = -0.0421, -0.0750, 0.1368
    bone.tail[:] = -0.0272, -0.0743, 0.1342
    bone.roll = -1.2633
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.R.001']]
    bones['brow.B.R.002'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.002')
    bone.head[:] = -0.0400, -0.0757, 0.1285
    bone.tail[:] = -0.0268, -0.0767, 0.1258
    bone.roll = -1.1877
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.R.001']]
    bones['lid.T.R.002'] = bone.name
    bone = arm.edit_bones.new('jaw.L.001')
    bone.head[:] = 0.0639, -0.0352, 0.0457
    bone.tail[:] = 0.0341, -0.0661, 0.0110
    bone.roll = 0.0793
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['jaw.L']]
    bones['jaw.L.001'] = bone.name
    bone = arm.edit_bones.new('jaw.R.001')
    bone.head[:] = -0.0569, -0.0352, 0.0457
    bone.tail[:] = -0.0271, -0.0661, 0.0110
    bone.roll = -0.0793
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['jaw.R']]
    bones['jaw.R.001'] = bone.name
    bone = arm.edit_bones.new('nose.L')
    bone.head[:] = 0.0184, -0.0767, 0.1127
    bone.tail[:] = 0.0174, -0.0908, 0.0816
    bone.roll = 0.0997
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.T.L.001']]
    bones['nose.L'] = bone.name
    bone = arm.edit_bones.new('nose.R')
    bone.head[:] = -0.0114, -0.0767, 0.1127
    bone.tail[:] = -0.0104, -0.0908, 0.0816
    bone.roll = -0.0997
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.T.R.001']]
    bones['nose.R'] = bone.name
    bone = arm.edit_bones.new('tongue.002')
    bone.head[:] = 0.0044, -0.0502, 0.0473
    bone.tail[:] = 0.0035, -0.0353, 0.0401
    bone.roll = 0.0295
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['tongue.001']]
    bones['tongue.002'] = bone.name
    bone = arm.edit_bones.new('ear.R.002')
    bone.head[:] = -0.0914, 0.0173, 0.1326
    bone.tail[:] = -0.0791, 0.0043, 0.0876
    bone.roll = 0.6486
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.R.001']]
    bones['ear.R.002'] = bone.name
    bone = arm.edit_bones.new('nose.003')
    bone.head[:] = 0.0035, -0.0983, 0.0730
    bone.tail[:] = 0.0035, -0.0971, 0.0626
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['nose.002']]
    bones['nose.003'] = bone.name
    bone = arm.edit_bones.new('ear.L.003')
    bone.head[:] = 0.0861, 0.0043, 0.0876
    bone.tail[:] = 0.0762, -0.0051, 0.0936
    bone.roll = 2.6192
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.L.002']]
    bones['ear.L.003'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.003')
    bone.head[:] = 0.0342, -0.0743, 0.1342
    bone.tail[:] = 0.0210, -0.0726, 0.1251
    bone.roll = 1.3752
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.L.002']]
    bones['brow.B.L.003'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.003')
    bone.head[:] = 0.0338, -0.0767, 0.1258
    bone.tail[:] = 0.0242, -0.0743, 0.1182
    bone.roll = 1.3092
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.L.002']]
    bones['lid.T.L.003'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.003')
    bone.head[:] = -0.0272, -0.0743, 0.1342
    bone.tail[:] = -0.0140, -0.0726, 0.1251
    bone.roll = -1.3752
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.B.R.002']]
    bones['brow.B.R.003'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.003')
    bone.head[:] = -0.0268, -0.0767, 0.1258
    bone.tail[:] = -0.0172, -0.0743, 0.1182
    bone.roll = -1.3092
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.R.002']]
    bones['lid.T.R.003'] = bone.name
    bone = arm.edit_bones.new('chin.L')
    bone.head[:] = 0.0341, -0.0661, 0.0110
    bone.tail[:] = 0.0313, -0.0803, 0.0535
    bone.roll = -0.2078
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['jaw.L.001']]
    bones['chin.L'] = bone.name
    bone = arm.edit_bones.new('chin.R')
    bone.head[:] = -0.0271, -0.0661, 0.0110
    bone.tail[:] = -0.0243, -0.0803, 0.0535
    bone.roll = 0.2078
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['jaw.R.001']]
    bones['chin.R'] = bone.name
    bone = arm.edit_bones.new('nose.L.001')
    bone.head[:] = 0.0174, -0.0908, 0.0816
    bone.tail[:] = 0.0035, -0.1176, 0.0833
    bone.roll = 1.7754
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['nose.L']]
    bones['nose.L.001'] = bone.name
    bone = arm.edit_bones.new('nose.R.001')
    bone.head[:] = -0.0104, -0.0908, 0.0816
    bone.tail[:] = 0.0035, -0.1176, 0.0833
    bone.roll = -1.7754
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['nose.R']]
    bones['nose.R.001'] = bone.name
    bone = arm.edit_bones.new('tongue.003')
    bone.head[:] = 0.0035, -0.0353, 0.0401
    bone.tail[:] = 0.0035, -0.0234, 0.0264
    bone.roll = 0.0002
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['tongue.002']]
    bones['tongue.003'] = bone.name
    bone = arm.edit_bones.new('ear.R.003')
    bone.head[:] = -0.0791, 0.0043, 0.0876
    bone.tail[:] = -0.0692, -0.0051, 0.0936
    bone.roll = -2.6192
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['ear.R.002']]
    bones['ear.R.003'] = bone.name
    bone = arm.edit_bones.new('lid.B.L')
    bone.head[:] = 0.0242, -0.0743, 0.1182
    bone.tail[:] = 0.0346, -0.0748, 0.1152
    bone.roll = -1.2158
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.L.003']]
    bones['lid.B.L'] = bone.name
    bone = arm.edit_bones.new('lid.B.R')
    bone.head[:] = -0.0172, -0.0743, 0.1182
    bone.tail[:] = -0.0276, -0.0748, 0.1152
    bone.roll = 1.2158
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.T.R.003']]
    bones['lid.B.R'] = bone.name
    bone = arm.edit_bones.new('cheek.B.L')
    bone.head[:] = 0.0313, -0.0803, 0.0535
    bone.tail[:] = 0.0617, -0.0583, 0.0669
    bone.roll = -1.4742
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['chin.L']]
    bones['cheek.B.L'] = bone.name
    bone = arm.edit_bones.new('cheek.B.R')
    bone.head[:] = -0.0243, -0.0803, 0.0535
    bone.tail[:] = -0.0547, -0.0583, 0.0669
    bone.roll = 1.4742
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['chin.R']]
    bones['cheek.B.R'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.001')
    bone.head[:] = 0.0346, -0.0748, 0.1152
    bone.tail[:] = 0.0472, -0.0743, 0.1136
    bone.roll = -1.1899
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.L']]
    bones['lid.B.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.001')
    bone.head[:] = -0.0276, -0.0748, 0.1152
    bone.tail[:] = -0.0402, -0.0743, 0.1136
    bone.roll = 1.1899
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.R']]
    bones['lid.B.R.001'] = bone.name
    bone = arm.edit_bones.new('cheek.B.L.001')
    bone.head[:] = 0.0617, -0.0583, 0.0669
    bone.tail[:] = 0.0706, -0.0365, 0.1165
    bone.roll = 3.2680
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.B.L']]
    bones['cheek.B.L.001'] = bone.name
    bone = arm.edit_bones.new('cheek.B.R.001')
    bone.head[:] = -0.0547, -0.0583, 0.0669
    bone.tail[:] = -0.0636, -0.0365, 0.1165
    bone.roll = -3.2680
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.B.R']]
    bones['cheek.B.R.001'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.002')
    bone.head[:] = 0.0472, -0.0743, 0.1136
    bone.tail[:] = 0.0584, -0.0690, 0.1180
    bone.roll = -1.3662
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.L.001']]
    bones['lid.B.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.002')
    bone.head[:] = -0.0402, -0.0743, 0.1136
    bone.tail[:] = -0.0514, -0.0690, 0.1180
    bone.roll = 1.3662
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.R.001']]
    bones['lid.B.R.002'] = bone.name
    bone = arm.edit_bones.new('brow.T.L')
    bone.head[:] = 0.0706, -0.0365, 0.1165
    bone.tail[:] = 0.0692, -0.0581, 0.1398
    bone.roll = -2.2526
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.B.L.001']]
    bones['brow.T.L'] = bone.name
    bone = arm.edit_bones.new('brow.T.R')
    bone.head[:] = -0.0636, -0.0365, 0.1165
    bone.tail[:] = -0.0622, -0.0581, 0.1398
    bone.roll = 2.2526
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['cheek.B.R.001']]
    bones['brow.T.R'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.003')
    bone.head[:] = 0.0584, -0.0690, 0.1180
    bone.tail[:] = 0.0643, -0.0585, 0.1226
    bone.roll = -1.2999
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.L.002']]
    bones['lid.B.L.003'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.003')
    bone.head[:] = -0.0514, -0.0690, 0.1180
    bone.tail[:] = -0.0573, -0.0585, 0.1226
    bone.roll = 1.2999
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['lid.B.R.002']]
    bones['lid.B.R.003'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.001')
    bone.head[:] = 0.0692, -0.0581, 0.1398
    bone.tail[:] = 0.0500, -0.0768, 0.1492
    bone.roll = 2.3471
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.L']]
    bones['brow.T.L.001'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.001')
    bone.head[:] = -0.0622, -0.0581, 0.1398
    bone.tail[:] = -0.0430, -0.0768, 0.1492
    bone.roll = -2.3471
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.R']]
    bones['brow.T.R.001'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.002')
    bone.head[:] = 0.0500, -0.0768, 0.1492
    bone.tail[:] = 0.0205, -0.0876, 0.1457
    bone.roll = 1.4396
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.L.001']]
    bones['brow.T.L.002'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.002')
    bone.head[:] = -0.0430, -0.0768, 0.1492
    bone.tail[:] = -0.0135, -0.0876, 0.1457
    bone.roll = -1.4396
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.R.001']]
    bones['brow.T.R.002'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.003')
    bone.head[:] = 0.0205, -0.0876, 0.1457
    bone.tail[:] = 0.0035, -0.0905, 0.1293
    bone.roll = 0.6318
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.L.002']]
    bones['brow.T.L.003'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.003')
    bone.head[:] = -0.0135, -0.0876, 0.1457
    bone.tail[:] = 0.0035, -0.0905, 0.1293
    bone.roll = -0.6318
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['brow.T.R.002']]
    bones['brow.T.R.003'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['head']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.name = "face"
    except AttributeError:
        pass
    try:
        pbone.gamerig.secondary_layers = [False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['nose']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['temple.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['temple.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['eye.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['eye.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.003']]
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
