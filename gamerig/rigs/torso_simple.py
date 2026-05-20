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
    """Simple torso rig with only upper and lower body bones (no neck/head).
    Suitable for Roblox-style characters or any rig that only needs a hips/chest split.
    """

    def __init__(self, obj, bone_name, metabone):
        eb = obj.data.edit_bones

        self.obj          = obj
        self.org_bones    = [bone_name] + connected_children_names(obj, bone_name)
        self.params       = metabone.gamerig
        self.spine_length = sum([eb[b].length for b in self.org_bones])

        self.root_bone_parent = eb[self.org_bones[0]].parent.name if eb[self.org_bones[0]].parent else None
        self.stretchable_tweak = self.params.stretchable_tweak

        if len(self.org_bones) < 2:
            raise MetarigError(
                "GAMERIG ERROR: %s : need at least 2 bones (lower and upper torso)" % bone_name
            )

        self.has_head = len(self.org_bones) >= 3


    def orient_bone(self, eb, axis, scale, reverse=False):
        v = Vector((0, 0, 0))
        setattr(v, axis, scale)

        if reverse:
            tail_vec = v @ self.obj.matrix_world
            eb.head[:] = eb.tail
            eb.tail[:] = eb.head + tail_vec
        else:
            tail_vec = v @ self.obj.matrix_world
            eb.tail[:] = eb.head + tail_vec


    def create_pivot(self):
        org_bones  = self.org_bones
        pivot_name = org_bones[0]
        eb = self.obj.data.edit_bones

        ctrl_name = copy_bone(self.obj, pivot_name, ctrlname('torso'))
        ctrl_eb   = eb[ctrl_name]
        self.orient_bone(ctrl_eb, 'y', self.spine_length / 2.5)

        mch_name = copy_bone(self.obj, ctrl_name, mchname('pivot'))
        mch_eb   = eb[mch_name]
        mch_eb.length /= 4

        pivot_loc = (eb[org_bones[0]].head + eb[org_bones[0]].tail) / 2
        put_bone(self.obj, ctrl_name, pivot_loc)

        return {'ctrl': ctrl_name, 'mch': mch_name}


    def create_head( self, head_bone ):
        eb = self.obj.data.edit_bones

        # Create head control
        head = copy_bone( self.obj, head_bone, ctrlname('head') )

        # MCH bones

        # Head MCH rotation
        mch_head = copy_bone(self.obj, head, mchname('ROT-head'))

        self.orient_bone( eb[mch_head], 'y', self.spine_length / 10 )

        mch = []

        # Tweak bone at head base (upper/head junction)
        twk_name = copy_bone(self.obj, head_bone, ctrlname("tweak_" + head_bone))
        eb[twk_name].length /= 2

        return {
            'ctrl'      : head,
            'mch_head'  : mch_head,
            'mch'       : mch,
            'tweak'     : [twk_name]
        }


    def create_upper(self, upper_bone):
        eb = self.obj.data.edit_bones

        chest = copy_bone(self.obj, upper_bone, ctrlname('chest'))
        self.orient_bone(eb[chest], 'y', self.spine_length / 3)

        mch_wgt = copy_bone(self.obj, upper_bone, mchname('chest'))

        twk, mch = [], []
        mch_name = copy_bone(self.obj, upper_bone, mchname(upper_bone))
        self.orient_bone(eb[mch_name], 'y', self.spine_length / 10)

        twk_name = copy_bone(self.obj, upper_bone, ctrlname("tweak_" + upper_bone))
        eb[twk_name].length /= 2

        mch.append(mch_name)
        twk.append(twk_name)

        return {'ctrl': chest, 'mch': mch, 'tweak': twk, 'mch_wgt': mch_wgt}


    def create_lower(self, lower_bone):
        eb = self.obj.data.edit_bones

        hips = copy_bone(self.obj, lower_bone, ctrlname('hips'))
        self.orient_bone(eb[hips], 'y', self.spine_length / 4, reverse=True)

        mch_wgt = copy_bone(self.obj, lower_bone, mchname('hips'))

        twk, mch = [], []
        mch_name = copy_bone(self.obj, lower_bone, mchname(lower_bone))
        self.orient_bone(eb[mch_name], 'y', self.spine_length / 10, reverse=True)

        twk_name = copy_bone(self.obj, lower_bone, ctrlname("tweak_" + lower_bone))
        eb[twk_name].length /= 2

        mch.append(mch_name)
        twk.append(twk_name)

        return {'ctrl': hips, 'mch': mch, 'tweak': twk, 'mch_wgt': mch_wgt}


    def parent_bones(self, bones):
        org_bones = self.org_bones
        eb = self.obj.data.edit_bones

        # Parent deform bones
        for i, b in enumerate(org_bones):
            if i == 0:
                if self.root_bone_parent:
                    eb[b].parent = eb[self.root_bone_parent]
            else:
                eb[b].parent      = eb[org_bones[i - 1]]
                eb[b].use_connect = True

        # Torso control => original root
        eb[bones['pivot']['ctrl']].parent = eb[org_bones[0]].parent

        # Chest and hips controls => torso pivot
        eb[bones['upper']['ctrl']].parent = eb[bones['pivot']['ctrl']]
        eb[bones['lower']['ctrl']].parent = eb[bones['pivot']['ctrl']]

        if 'head' in bones:
            # Head control => MCH-rotation_head
            eb[bones['head']['ctrl']].parent     = eb[bones['head']['mch_head']]
            # Head MCH => upper ctrl (chest); head defaults to following chest rotation
            eb[bones['head']['mch_head']].parent = eb[bones['upper']['ctrl']]
            # Head tweak => last upper MCH (top of chest chain)
            for twk in bones['head']['tweak']:
                eb[twk].parent = eb[bones['upper']['mch'][-1]]

        # Upper MCH bones (forward chain from pivot)
        for i, b in enumerate(bones['upper']['mch']):
            if i == 0:
                eb[b].parent = eb[bones['pivot']['ctrl']]
            else:
                eb[b].parent = eb[bones['upper']['mch'][i - 1]]

        # Lower MCH bones (reverse chain, last MCH parents to pivot)
        for i, b in enumerate(bones['lower']['mch']):
            if i == len(bones['lower']['mch']) - 1:
                eb[b].parent = eb[bones['pivot']['ctrl']]
            else:
                eb[b].parent = eb[bones['lower']['mch'][i + 1]]

        # MCH pivot
        eb[bones['pivot']['mch']].parent = eb[bones['upper']['mch'][0]]

        # MCH widgets
        eb[bones['upper']['mch_wgt']].parent = eb[bones['upper']['mch'][-1]]
        eb[bones['lower']['mch_wgt']].parent = eb[bones['lower']['mch'][0]]

        # Upper tweaks
        for twk, mch in zip(bones['upper']['tweak'], bones['upper']['mch']):
            if bones['upper']['tweak'].index(twk) == 0:
                eb[twk].parent = eb[bones['pivot']['mch']]
            else:
                eb[twk].parent = eb[mch]

        # Lower tweaks
        for i, twk in enumerate(bones['lower']['tweak']):
            if i == 0:
                eb[twk].parent = eb[bones['lower']['mch'][i]]
            else:
                eb[twk].parent = eb[bones['lower']['mch'][i - 1]]


    def make_constraint(self, bone, constraint):
        pb = self.obj.pose.bones

        owner_pb     = pb[bone]
        const        = owner_pb.constraints.new(constraint['constraint'])
        const.target = self.obj

        for p in [k for k in constraint.keys() if k in dir(const)]:
            setattr(const, p, constraint[p])


    def constrain_bones(self, bones):
        # Upper and lower MCH bones
        for l in [bones['upper'], bones['lower']]:
            mch    = l['mch']
            factor = float(1 / len(l['tweak']))
            for b in mch:
                self.make_constraint(b, {
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : l['ctrl'],
                    'influence'   : factor,
                    'owner_space' : 'LOCAL',
                    'target_space': 'LOCAL',
                })

        # MCH pivot
        self.make_constraint(bones['pivot']['mch'], {
            'constraint'  : 'COPY_TRANSFORMS',
            'subtarget'   : bones['lower']['mch'][-1],
            'owner_space' : 'LOCAL',
            'target_space': 'LOCAL',
        })

        # Head MCH constraints
        if 'head' in bones:
            self.make_constraint(bones['head']['mch_head'], {
                'constraint': 'COPY_ROTATION',
                'subtarget' : bones['pivot']['ctrl'],
            })
            self.make_constraint(bones['head']['mch_head'], {
                'constraint': 'COPY_SCALE',
                'subtarget' : bones['pivot']['ctrl'],
            })

        # Deform bones
        tweaks = bones['lower']['tweak'] + bones['upper']['tweak']
        if 'head' in bones:
            tweaks        = tweaks + bones['head']['tweak']
            org_for_deform = self.org_bones[:-1]
        else:
            org_for_deform = self.org_bones

        for d, t in zip(org_for_deform, tweaks):
            tidx = tweaks.index(t)
            self.make_constraint(d, {
                'constraint': 'COPY_TRANSFORMS',
                'subtarget' : t,
            })
            if tidx != len(tweaks) - 1:
                self.make_constraint(d, {
                    'constraint': 'DAMPED_TRACK',
                    'subtarget' : tweaks[tidx + 1],
                })
                if self.stretchable_tweak:
                    self.make_constraint(d, {
                        'constraint': 'STRETCH_TO',
                        'subtarget' : tweaks[tidx + 1],
                    })

        # Head deform bone directly follows head control
        if 'head' in bones:
            self.make_constraint(self.org_bones[-1], {
                'constraint': 'COPY_TRANSFORMS',
                'subtarget' : bones['head']['ctrl'],
            })


    def create_drivers(self, bones):
        pb = self.obj.pose.bones

        # Head Follow driver
        if 'head' in bones:
            torso = pb[bones['pivot']['ctrl']]
            prop  = 'Head Follow'
            torso[prop] = 0.0
            rna_idprop_ui_create(torso, prop, default=0.0, description=prop, overridable=True)

            drv = pb[bones['head']['mch_head']].constraints[0].driver_add("influence").driver
            drv.type = 'AVERAGE'

            var = drv.variables.new()
            var.name = 'head_follow'
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = torso.path_from_id() + '["Head Follow"]'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers.new('GENERATOR')
            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

        if self.stretchable_tweak:
            tweak_bones = bones['lower']['tweak'] + bones['upper']['tweak']
            if 'head' in bones:
                tweak_bones = tweak_bones + bones['head']['tweak']
            org_for_deform = self.org_bones[:-1] if 'head' in bones else self.org_bones

            for bone, t in zip(org_for_deform, tweak_bones):
                rna_idprop_ui_create(pb[t], 'Tweak Stretch', default=1.0, description='Tweak Stretch', overridable=True)

                tidx = tweak_bones.index(t)
                if tidx != len(tweak_bones) - 1:
                    drv = pb[bone].constraints['Stretch To'].driver_add("influence").driver
                    drv.type = 'SUM'

                    var = drv.variables.new()
                    var.name = 'tweak_stretch'
                    var.type = "SINGLE_PROP"
                    var.targets[0].id = self.obj
                    var.targets[0].data_path = pb[t].path_from_id() + '["Tweak Stretch"]'


    def locks_and_widgets(self, bones):
        pb = self.obj.pose.bones

        tweaks = bones['lower']['tweak'] + bones['upper']['tweak']
        if 'head' in bones:
            tweaks = tweaks + bones['head']['tweak']

        for bone in tweaks:
            pb[bone].rotation_mode = 'ZXY'
            pb[bone].lock_rotation = True, False, True
            pb[bone].lock_scale    = False, True, False

        create_torso_widget(self.obj, bones['pivot']['ctrl'])

        for bone in [bones['upper']['ctrl'], bones['lower']['ctrl']]:
            create_directed_circle_widget(self.obj, bone, radius=1.0, head_tail=0.5)

        pb[bones['upper']['ctrl']].custom_shape_transform = pb[bones['upper']['mch_wgt']]
        pb[bones['lower']['ctrl']].custom_shape_transform = pb[bones['lower']['mch_wgt']]

        if 'head' in bones:
            create_directed_circle_widget(self.obj, bones['head']['ctrl'], radius=0.75, head_tail=1.0)

        for bone in tweaks:
            create_sphere_widget(self.obj, bone)
            move_bone_collection_to(self.obj, bone, self.params.tweak_bone_collection)


    def generate(self, context):
        eb = self.obj.data.edit_bones

        for bone in self.org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        lower_bone = basename(self.org_bones[0])
        upper_bone = basename(self.org_bones[1])

        bones = {}
        bones['pivot'] = self.create_pivot()
        bones['upper'] = self.create_upper(upper_bone)
        bones['lower'] = self.create_lower(lower_bone)

        if self.has_head:
            head_bone      = basename(self.org_bones[2])
            bones['head']  = self.create_head(head_bone)

        self.parent_bones(bones)
        self.bones = bones

        chest_ctrl = bones['upper']['ctrl']
        hips_ctrl  = bones['lower']['ctrl']
        pivot_ctrl = bones['pivot']['ctrl']

        controls = [chest_ctrl, hips_ctrl, pivot_ctrl]
        if self.has_head:
            controls.append(bones['head']['ctrl'])
        controls_string = ", ".join(["'" + x + "'" for x in controls])

        head_follow_ui = ""
        if self.has_head:
            head_follow_ui = (
                "if is_selected( controls ):\n"
                "    layout.prop( pose_bones[ '" + pivot_ctrl + "' ], '[\"Head Follow\"]',"
                " text='Head Follow (" + self.org_bones[2] + ")', slider = True )\n"
            )

        head_op_prop = ""
        if self.has_head:
            head_op_prop = "    props.head  = '" + bones['head']['ctrl'] + "'\n"

        tweak_ui = ""
        if self.stretchable_tweak:
            tweak_list_bones = bones['lower']['tweak'] + bones['upper']['tweak']
            if 'head' in bones:
                tweak_list_bones = tweak_list_bones + bones['head']['tweak']
            tweak_list = str(tweak_list_bones)
            tweak_ui = (
                "tweaks = " + tweak_list + "\n"
                "for tweak in tweaks:\n"
                "    if is_selected( tweak ):\n"
                "        layout.prop( pose_bones[ tweak ], '[\"Tweak Stretch\"]',"
                " text='Tweak Stretch (' + tweak + ')', slider = True )\n"
            )

        return (
            "controls = [" + controls_string + "]\n"
            + head_follow_ui
            + tweak_ui
            + "if is_selected( controls ):\n"
            + "    props = layout.operator(SimpleTorso_Align2Floor.bl_idname,"
            + " text='Align To Floor (" + self.org_bones[0] + ")', icon='SNAP_ON')\n"
            + "    props.chest = '" + chest_ctrl + "'\n"
            + "    props.hips  = '" + hips_ctrl  + "'\n"
            + "    props.pivot = '" + pivot_ctrl  + "'\n"
            + head_op_prop
            + "    props = layout.operator(SimpleTorso_AlignYaw.bl_idname,"
            + " text='Align Yaw (" + self.org_bones[0] + ")', icon='SNAP_ON')\n"
            + "    props.chest = '" + chest_ctrl + "'\n"
            + "    props.hips  = '" + hips_ctrl  + "'\n"
            + "    props.pivot = '" + pivot_ctrl  + "'\n"
            + head_op_prop
        )


    def postprocess(self, context):
        self.constrain_bones(self.bones)
        self.create_drivers(self.bones)
        self.locks_and_widgets(self.bones)


def operator_script(rig_id):
    return '''

class SimpleTorso_Align2Floor(bpy.types.Operator):
    """ Align simple torso rig to horizontal plane.
    """
    bl_idname = "gamerig.simple_torso_align_to_floor_{rig_id}"
    bl_label = "Align Pivot To Floor"
    bl_description = "Align pivot to horizontal plane"
    bl_options = {{"UNDO", "INTERNAL"}}

    pivot : bpy.props.StringProperty(name="Pivot Name")
    hips  : bpy.props.StringProperty(name="Hips Name")
    chest : bpy.props.StringProperty(name="Chest Name")
    head  : bpy.props.StringProperty(name="Head Name", default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == \'POSE\'

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            obj = context.active_object

            pivot = obj.pose.bones[self.pivot]
            hips  = obj.pose.bones[self.hips]
            chest = obj.pose.bones[self.chest]
            head  = obj.pose.bones[self.head] if self.head else None

            org_hips_mat  = hips.matrix.copy()
            org_chest_mat = chest.matrix.copy()
            org_head_mat  = head.matrix.copy() if head else None

            # Align pivot to horizontal plane
            loc, rot, scl = pivot.matrix.decompose()
            euler = rot.to_euler(\'XYZ\')
            euler.x = euler.y = 0.0
            rot = euler.to_quaternion()
            pivot_mat = get_pose_matrix_in_other_space(Matrix.LocRotScale(loc, rot, scl), pivot)
            set_pose_rotation(pivot, pivot_mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, pivot)

            mat = get_pose_matrix_in_other_space(org_hips_mat, hips)
            set_pose_rotation(hips, mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, hips)

            mat = get_pose_matrix_in_other_space(org_chest_mat, chest)
            set_pose_rotation(chest, mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, chest)

            if head:
                mat = get_pose_matrix_in_other_space(org_head_mat, head)
                set_pose_rotation(head, mat)
                bpy.ops.object.mode_set(mode=\'OBJECT\')
                bpy.ops.object.mode_set(mode=\'POSE\')
                insert_keyframe_by_mode(context, head)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{"FINISHED"}}


class SimpleTorso_AlignYaw(bpy.types.Operator):
    """ Snap simple torso yaw to nearest 90 degrees.
    """
    bl_idname = "gamerig.simple_torso_align_yaw_{rig_id}"
    bl_label = "Align Yaw"
    bl_description = "Align pivot to nearest vertical plane"
    bl_options = {{"UNDO", "INTERNAL"}}

    pivot : bpy.props.StringProperty(name="Pivot Name")
    hips  : bpy.props.StringProperty(name="Hips Name")
    chest : bpy.props.StringProperty(name="Chest Name")
    head  : bpy.props.StringProperty(name="Head Name", default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == \'POSE\'

    def execute(self, context):
        from math import floor, radians
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            obj = context.active_object

            pivot = obj.pose.bones[self.pivot]
            hips  = obj.pose.bones[self.hips]
            chest = obj.pose.bones[self.chest]
            head  = obj.pose.bones[self.head] if self.head else None

            org_hips_mat  = hips.matrix.copy()
            org_chest_mat = chest.matrix.copy()
            org_head_mat  = head.matrix.copy() if head else None

            # Snap pivot yaw to nearest 90 deg
            loc, rot, scl = pivot.matrix.decompose()
            euler = rot.to_euler(\'XYZ\')
            if euler.z >= 0.0:
                euler.z = floor((euler.z + radians(45)) / radians(90)) * radians(90)
            else:
                euler.z = -(floor((-euler.z + radians(45)) / radians(90)) * radians(90))
            rot = euler.to_quaternion()
            pivot_mat = get_pose_matrix_in_other_space(Matrix.LocRotScale(loc, rot, scl), pivot)
            set_pose_rotation(pivot, pivot_mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, pivot)

            mat = get_pose_matrix_in_other_space(org_hips_mat, hips)
            set_pose_rotation(hips, mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, hips)

            mat = get_pose_matrix_in_other_space(org_chest_mat, chest)
            set_pose_rotation(chest, mat)
            bpy.ops.object.mode_set(mode=\'OBJECT\')
            bpy.ops.object.mode_set(mode=\'POSE\')
            insert_keyframe_by_mode(context, chest)

            if head:
                mat = get_pose_matrix_in_other_space(org_head_mat, head)
                set_pose_rotation(head, mat)
                bpy.ops.object.mode_set(mode=\'OBJECT\')
                bpy.ops.object.mode_set(mode=\'POSE\')
                insert_keyframe_by_mode(context, head)

        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {{"FINISHED"}}


classes.append(SimpleTorso_Align2Floor)
classes.append(SimpleTorso_AlignYaw)

'''.format(rig_id=rig_id)


def add_parameters(params):
    """ Add the parameters of this rig type to the RigParameters PropertyGroup
    """
    params.stretchable_tweak = bpy.props.BoolProperty(
        name        = "Stretchable Tweak",
        default     = True,
        description = "Allow stretch to tweak controllers"
    )

    params.tweak_bone_collection = bpy.props.StringProperty(
        name        = "Tweak Bone Collection",
        description = "Bone collection for the tweak controls to be on",
        default     = "Torso (Tweak)"
    )


def create_torso_widget(rig, bone_name, size=1, bone_transform_name=None):
    """ Creates a torso cube widget.
    """
    obj = create_widget(rig, bone_name, bone_transform_name)
    if obj is not None:
        verts = [
            ( 0.5*size,  0.5*size,  0.5*size), ( 0.5*size, -0.5*size,  0.5*size),
            (-0.5*size, -0.5*size,  0.5*size), (-0.5*size,  0.5*size,  0.5*size),
            ( 0.5*size,  0.5*size, -0.5*size), ( 0.5*size, -0.5*size, -0.5*size),
            (-0.5*size, -0.5*size, -0.5*size), (-0.5*size,  0.5*size, -0.5*size),
            (-0.049471*size, -0.54198*size, 0.4719*size),
            ( 0.047116*size, -0.54198*size, 0.4719*size),
            (-0.0002994*size, -0.59993*size, 0.4719*size),
        ]
        edges = [
            (0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
            (0,4),(1,5),(2,6),(3,7),(8,9),(9,10),(10,8),
        ]
        mesh = obj.data
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        return obj
    return None


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
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

    bone = arm.edit_bones.new('upper_body')
    bone.head[:] = 0.0000, -0.0037, 0.2256
    bone.tail[:] = 0.0000, -0.0045, 0.4748
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['hips']]
    bones['upper_body'] = bone.name

    bone = arm.edit_bones.new('head')
    bone.head[:] = 0.0000, -0.0045, 0.4748
    bone.tail[:] = 0.0000, -0.0045, 0.6500
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_body']]
    bones['head'] = bone.name

    if "Torso" not in arm.collections.keys():
        arm.collections.new("Torso")
    if "Torso (Tweak)" not in arm.collections.keys():
        arm.collections.new("Torso (Tweak)")

    bpy.ops.object.mode_set(mode='OBJECT')

    pbone = obj.pose.bones[bones['hips']]
    pbone.gamerig.name = 'torso_simple'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.gamerig.stretchable_tweak = True
    except AttributeError:
        pass
    try:
        pbone.gamerig.tweak_bone_collection = "Torso (Tweak)"
    except AttributeError:
        pass

    pbone = obj.pose.bones[bones['upper_body']]
    pbone.gamerig.name = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    pbone = obj.pose.bones[bones['head']]
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
