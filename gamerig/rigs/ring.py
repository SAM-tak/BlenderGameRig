import bpy, re, mathutils
from rna_prop_ui import rna_idprop_ui_prop_get
from ..utils import (
    copy_bone, flip_bone, ctrlname, mchname, basename, connected_children_names,
    insert_before_first_period,
    create_widget,
    MetarigError
)
from .widgets import create_upper_arc_widget, create_lower_arc_widget, create_left_arc_widget, create_right_arc_widget


class Rig:

    def __init__(self, obj, bone_name, metabone):
        self.obj = obj
        self.params = metabone.gamerig
        self.switchable_rig = len(metabone.constraints) > 0
        
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)

        if self.params.symmetry:
            m = re.search(r'(\W)(L|R)(\.\d+)?$', bone_name)
            if m:
                lr = 'R' if m.group(2) == 'L' else 'L'
                ext = m.group(3) if m.group(3) else ''
                counterpart = re.sub(m.group(1) + m.group(2) + ext + '$', m.group(1) + lr + ext, bone_name)
                if obj.data.bones[counterpart]:
                    cps = connected_children_names(obj, counterpart)
                    cps.reverse()
                    cps.append(counterpart)
                    self.org_bones += cps

        if len(self.org_bones) <= 3:
            raise MetarigError(
                "GAMERIG ERROR: invalid rig structure, chain length too short : rig '%s'" % bone_name
            )


    def make_controls( self ):
        eb = self.obj.data.edit_bones

        ctrls = []

        center =  mathutils.Vector((0,0,0))
        for org in self.org_bones:
            center += eb[org].head
            center += eb[org].tail
        center /= len(self.org_bones) * 2

        if self.params.symmetry:
            l = 0
            for org in self.org_bones[:int(len(self.org_bones) / 2) + 1] + self.org_bones[int(len(self.org_bones) / 2):-1]:
                if l == 0:
                    ctrl_bone = copy_bone(self.obj, org, ctrlname(re.sub(r'L|R(\.?\d*)$', r'T\1', self.org_bones[0])))
                elif l == int(len(self.org_bones) / 2):
                    ctrl_bone = copy_bone(self.obj, org, ctrlname(re.sub(r'L|R(\.?\d*)$', r'B\1', self.org_bones[0])))
                else:
                    ctrl_bone = copy_bone(self.obj, org, ctrlname(org))
                eb[ctrl_bone].use_connect = False
                if l == int(len(self.org_bones) / 2):
                    flip_bone(self.obj, ctrl_bone)
                eb[ctrl_bone].tail = eb[ctrl_bone].head + (eb[ctrl_bone].head - center).normalized() * eb[ctrl_bone].length
                eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

                ctrls.append( ctrl_bone )
                l += 1
        else:
            for org in self.org_bones:
                ctrl_bone = copy_bone(self.obj, org, ctrlname(org))
                eb[ctrl_bone].use_connect = False
                eb[ctrl_bone].tail = eb[ctrl_bone].head + (eb[ctrl_bone].head - center).normalized() * eb[ctrl_bone].length
                eb[ctrl_bone].parent = eb[self.org_bones[0]].parent

                ctrls.append( ctrl_bone )

        return ctrls

    def make_mchs( self ):
        eb = self.obj.data.edit_bones

        mchs = []
        parents = self.ctrls
        
        if self.params.symmetry:
            parents = self.ctrls[:int(len(self.ctrls)/2)] + self.ctrls[int(len(self.ctrls)/2) + 1:]
            parents.append(self.ctrls[0])
        
        for org, parent in zip(self.org_bones, parents):
            mch_bone = copy_bone(self.obj, org, mchname(org))
            eb[mch_bone].use_connect = False
            eb[mch_bone].parent = eb[parent]
            mchs.append( mch_bone )

        return mchs


    def make_constraints( self, context ):

        org_bones = self.org_bones
        pb        = self.obj.pose.bones

        # org bones' constraints
        ctrls = self.ctrls
        mchs = self.mchs

        qs = (0, int(len(ctrls) / 4), int(len(ctrls) / 2), int(len(ctrls) * 3 / 4), len(ctrls))
        for i in range(0, len(ctrls)):
            for j in range(0, 4):
                if qs[j] < i and i < qs[j + 1]:
                    self.make_constraint( ctrls[i], {
                        'constraint'   : 'COPY_LOCATION',
                        'subtarget'    : ctrls[qs[j]],
                        'target_space' : 'LOCAL',
                        'owner_space'  : 'LOCAL',
                        'use_offset'   : True,
                        'influence'    : (i - qs[j]) / 2
                    })
                    self.make_constraint( ctrls[i], {
                        'constraint'   : 'COPY_LOCATION',
                        'subtarget'    : ctrls[qs[j + 1]] if qs[j + 1] < len(ctrls) else ctrls[0],
                        'target_space' : 'LOCAL',
                        'owner_space'  : 'LOCAL',
                        'use_offset'   : True,
                        'influence'    : (qs[j + 1] - i) / 2
                    })
                    break

        # mch chain
        subtargets = ctrls[1:int(len(self.ctrls)/2) + 1] + ctrls[int(len(self.ctrls)/2):] if self.params.symmetry else ctrls[1:] + [ctrls[0]]
        for mchb, subtarget in zip( mchs, subtargets ):
            self.make_constraint( mchb, {
                'constraint'  : 'DAMPED_TRACK',
                'subtarget'   : subtarget,
            })

            if self.params.stretchable:
                self.make_constraint( mchb, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : subtarget,
                })

        # bind original bone
        for org, mch in zip( org_bones, mchs ):
            stashed = self.stash_constraint(org)

            self.make_constraint( org, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : mch
            })
            
            self.unstash_constraint( org, stashed )

            if self.switchable_rig:
                if not 'Rig/Phy' in pb[ctrls[0]]:
                    # Create Rig/Physics switch property
                    pb[ctrls[0]]['Rig/Phy'] = 0.0
                    prop = rna_idprop_ui_prop_get( pb[ctrls[0]], 'Rig/Phy', create=True )
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

        if not self.switchable_rig:
            return ''
        else:
            return """
controls = %s

if is_selected( controls ):
""" % self.ctrls[0] + ("""
    layout.prop( pose_bones[ controls[0] ], '["Rig/Phy"]', text='Rig/Phy (' + controls[0] + ')', slider = True )
    props = layout.operator(Ring_Snap.bl_idname, text="Snap Ctrl->Target (" + controls[0] + ")", icon='SNAP_ON')
    props.ctrls = "%s"
    props.targets  = "%s"
""" % (self.ctrls, self.org_bones) if self.switchable_rig else '')


    def postprocess(self, context):
        pb = self.obj.pose.bones

        # Make widgets
        for ctrl in self.ctrls:
            create_upper_arc_widget(self.obj, ctrl)

        self.make_constraints(context)


def operator_script(rig_id):
    return '''
class Ring_Snap(bpy.types.Operator):
    """ Snaps controllers to Target Bone Position.
    """
    bl_idname = "gamerig.ring_snap_{rig_id}"
    bl_label = "Snap ring ctrls to Target"
    bl_description = "Snap ring controllers to target bone position (no keying)"
    bl_options = {{'UNDO', 'INTERNAL'}}

    ctrls : bpy.props.StringProperty(name="Ctrl Bone names")
    targets  : bpy.props.StringProperty(name="Target Bone names")

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

            ctrls  = eval(self.ctrls)
            targets  = eval(self.targets)

            for ctrl, target in zip(ctrls, targets):
                cb = obj.pose.bones[ctrl]
                tb = obj.pose.bones[target]
                match_pose_translation(cb, tb)
                match_pose_scale(cb, tb)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


classes.append(Ring_Snap)


'''.format(rig_id=rig_id)


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.symmetry = bpy.props.BoolProperty(
        name        = "Symmetry",
        default     = False,
        description = "Add symmetry counterpatrs to chain"
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "symmetry")


def create_sample(obj):
    # generated by gamerig.utils.write_metarig

    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.4000, 0.3333, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = False
    bones['Bone'] = bone.name
    bone = arm.edit_bones.new('Bone.002')
    bone.head[:] = 0.4000, 0.3333, 0.0000
    bone.tail[:] = 0.4000, 0.6667, 0.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = False
    bone.parent = arm.edit_bones[bones['Bone']]
    bones['Bone.002'] = bone.name
    bone = arm.edit_bones.new('Bone.001')
    bone.head[:] = 0.4000, 0.6667, 0.0000
    bone.tail[:] = 0.0000, 1.0000, 0.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = False
    bone.parent = arm.edit_bones[bones['Bone.002']]
    bones['Bone.001'] = bone.name
    bone = arm.edit_bones.new('Bone.003')
    bone.head[:] = 0.0000, 1.0000, 0.0000
    bone.tail[:] = -0.4000, 0.6667, 0.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['Bone.001']]
    bones['Bone.003'] = bone.name
    bone = arm.edit_bones.new('Bone.004')
    bone.head[:] = -0.4000, 0.6667, 0.0000
    bone.tail[:] = -0.4000, 0.3333, 0.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['Bone.003']]
    bones['Bone.004'] = bone.name
    bone = arm.edit_bones.new('Bone.005')
    bone.head[:] = -0.4000, 0.3333, 0.0000
    bone.tail[:] = 0.0000, 0.0000, 0.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.use_deform = True
    bone.parent = arm.edit_bones[bones['Bone.004']]
    bones['Bone.005'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bone']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.name = "ring"
    except AttributeError:
        pass
    try:
        pbone.gamerig.symmetry = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['Bone.002']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.001']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.003']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.004']]
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.005']]
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
