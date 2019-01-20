#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

# <pep8 compliant>

UI_TEMPLATE = '''
#
# for gamerig
#
import bpy
from mathutils import Matrix, Vector
from math import acos, pi, radians
from bpy.utils import register_class

############################
## Math utility functions ##
############################

def perpendicular_vector(v):
    """ Returns a vector that is perpendicular to the one given.
        The returned vector is _not_ guaranteed to be normalized.
    """
    # Create a vector that is not aligned with v.
    # It doesn't matter what vector.  Just any vector
    # that's guaranteed to not be pointing in the same
    # direction.
    if abs(v[0]) < abs(v[1]):
        tv = Vector((1,0,0))
    else:
        tv = Vector((0,1,0))

    # Use cross prouct to generate a vector perpendicular to
    # both tv and (more importantly) v.
    return v.cross(tv)


def rotation_difference(mat1, mat2):
    """ Returns the shortest-path rotational difference between two
        matrices.
    """
    q1 = mat1.to_quaternion()
    q2 = mat2.to_quaternion()
    angle = acos(min(1,max(-1,q1.dot(q2)))) * 2
    if angle > pi:
        angle = -angle + (2*pi)
    return angle

def tail_distance(angle,bone_ik,bone_fk):
    """ Returns the distance between the tails of two bones
        after rotating bone_ik in AXIS_ANGLE mode.
    """
    rot_mod=bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'
    bone_ik.rotation_axis_angle[0] = angle
    bpy.context.scene.update()

    dv = (bone_fk.tail - bone_ik.tail).length

    bone_ik.rotation_mode = rot_mod
    return dv

def find_min_range(bone_ik,bone_fk,f=tail_distance,delta=pi/8):
    """ finds the range where lies the minimum of function f applied on bone_ik and bone_fk
        at a certain angle.
    """
    rot_mod=bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'

    start_angle = bone_ik.rotation_axis_angle[0]
    angle = start_angle
    while (angle > (start_angle - 2*pi)) and (angle < (start_angle + 2*pi)):
        l_dist = f(angle-delta,bone_ik,bone_fk)
        c_dist = f(angle,bone_ik,bone_fk)
        r_dist = f(angle+delta,bone_ik,bone_fk)
        if min((l_dist,c_dist,r_dist)) == c_dist:
            bone_ik.rotation_mode = rot_mod
            return (angle-delta,angle+delta)
        else:
            angle=angle+delta

def ternarySearch(f, left, right, bone_ik, bone_fk, absolutePrecision):
    """
    Find minimum of unimodal function f() within [left, right]
    To find the maximum, revert the if/else statement or revert the comparison.
    """
    while True:
        #left and right are the current bounds; the maximum is between them
        if abs(right - left) < absolutePrecision:
            return (left + right)/2

        leftThird = left + (right - left)/3
        rightThird = right - (right - left)/3

        if f(leftThird, bone_ik, bone_fk) > f(rightThird, bone_ik, bone_fk):
            left = leftThird
        else:
            right = rightThird

#########################################
## "Visual Transform" helper functions ##
#########################################

def get_pose_matrix_in_other_space(mat, pose_bone):
    """ Returns the transform matrix relative to pose_bone's current
        transform space.  In other words, presuming that mat is in
        armature space, slapping the returned matrix onto pose_bone
        should give it the armature-space transforms of mat.
        TODO: try to handle cases with axis-scaled parents better.
    """
    rest = pose_bone.bone.matrix_local.copy()
    rest_inv = rest.inverted()
    if pose_bone.parent:
        par_mat = pose_bone.parent.matrix.copy()
        par_inv = par_mat.inverted()
        par_rest = pose_bone.parent.bone.matrix_local.copy()
    else:
        par_mat = Matrix()
        par_inv = Matrix()
        par_rest = Matrix()

    # Get matrix in bone's current transform space
    smat = rest_inv * (par_rest * (par_inv * mat))

    # Compensate for non-local location
    #if not pose_bone.bone.use_local_location:
    #    loc = smat.to_translation() * (par_rest.inverted() * rest).to_quaternion()
    #    smat.translation = loc

    return smat


def get_local_pose_matrix(pose_bone):
    """ Returns the local transform matrix of the given pose bone.
    """
    return get_pose_matrix_in_other_space(pose_bone.matrix, pose_bone)


def set_pose_translation(pose_bone, mat):
    """ Sets the pose bone's translation to the same translation as the given matrix.
        Matrix should be given in bone's local space.
    """
    if pose_bone.bone.use_local_location == True:
        pose_bone.location = mat.to_translation()
    else:
        loc = mat.to_translation()

        rest = pose_bone.bone.matrix_local.copy()
        if pose_bone.bone.parent:
            par_rest = pose_bone.bone.parent.matrix_local.copy()
        else:
            par_rest = Matrix()

        q = (par_rest.inverted() * rest).to_quaternion()
        pose_bone.location = q * loc


def set_pose_rotation(pose_bone, mat):
    """ Sets the pose bone's rotation to the same rotation as the given matrix.
        Matrix should be given in bone's local space.
    """
    q = mat.to_quaternion()

    if pose_bone.rotation_mode == 'QUATERNION':
        pose_bone.rotation_quaternion = q
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        pose_bone.rotation_axis_angle[0] = q.angle
        pose_bone.rotation_axis_angle[1] = q.axis[0]
        pose_bone.rotation_axis_angle[2] = q.axis[1]
        pose_bone.rotation_axis_angle[3] = q.axis[2]
    else:
        pose_bone.rotation_euler = q.to_euler(pose_bone.rotation_mode)


def set_pose_scale(pose_bone, mat):
    """ Sets the pose bone's scale to the same scale as the given matrix.
        Matrix should be given in bone's local space.
    """
    pose_bone.scale = mat.to_scale()


def match_pose_translation(pose_bone, target_bone):
    """ Matches pose_bone's visual translation to target_bone's visual
        translation.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    set_pose_translation(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def match_pose_rotation(pose_bone, target_bone):
    """ Matches pose_bone's visual rotation to target_bone's visual
        rotation.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    set_pose_rotation(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def match_pose_scale(pose_bone, target_bone):
    """ Matches pose_bone's visual scale to target_bone's visual
        scale.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    #set_pose_scale(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')

def correct_rotation(bone_ik, bone_fk):
    """ Corrects the ik rotation in ik2fk snapping functions
    """

    alfarange = find_min_range(bone_ik,bone_fk)
    alfamin = ternarySearch(tail_distance,alfarange[0],alfarange[1],bone_ik,bone_fk,0.1)

    rot_mod = bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'
    bone_ik.rotation_axis_angle[0] = alfamin
    bone_ik.rotation_mode = rot_mod

##############################
## IK/FK snapping functions ##
##############################

def fk2ik_arm(obj, fk, ik):
    """ Matches the fk bones in an arm rig to the ik bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    uarm  = obj.pose.bones[fk[0]]
    farm  = obj.pose.bones[fk[1]]
    hand  = obj.pose.bones[fk[2]]
    uarmi = obj.pose.bones[ik[0]]
    farmi = obj.pose.bones[ik[1]]
    handi = obj.pose.bones[ik[2]]

    # Upper arm position
    match_pose_translation(uarm, uarmi)
    match_pose_rotation(uarm, uarmi)
    match_pose_scale(uarm, uarmi)

    # Forearm position
    match_pose_translation(hand, handi)
    match_pose_rotation(farm, farmi)
    match_pose_scale(farm, farmi)

    # Hand position
    match_pose_translation(hand, handi)
    match_pose_rotation(hand, handi)
    match_pose_scale(hand, handi)

def ik2fk_arm(obj, fk, ik):
    """ Matches the ik bones in an arm rig to the fk bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    uarm  = obj.pose.bones[fk[0]]
    hand  = obj.pose.bones[fk[2]]
    uarmi = obj.pose.bones[ik[0]]
    handi = obj.pose.bones[ik[2]]

    # Hand position
    match_pose_translation(handi, hand)
    match_pose_rotation(handi, hand)
    match_pose_scale(handi, hand)

    # Upper Arm position
    match_pose_translation(uarmi, uarm)
    match_pose_rotation(uarmi, uarm)
    match_pose_scale(uarmi, uarm)

    # Rotation Correction
    correct_rotation(uarmi, uarm)

def fk2ik_leg(obj, fk, ik):
    """ Matches the fk bones in a leg rig to the ik bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    thigh  = obj.pose.bones[fk[0]]
    shin   = obj.pose.bones[fk[1]]
    foot   = obj.pose.bones[fk[2]]
    toe    = obj.pose.bones[fk[3]]
    thighi = obj.pose.bones[ik[0]]
    shini  = obj.pose.bones[ik[1]]
    footi  = obj.pose.bones[ik[2]]
    toei   = obj.pose.bones[ik[3]]

    # Thigh position
    match_pose_translation(thigh, thighi)
    match_pose_rotation(thigh, thighi)
    match_pose_scale(thigh, thighi)

    # Shin position
    match_pose_rotation(shin, shini)
    match_pose_scale(shin, shini)

    # Foot position
    mat = toe.bone.matrix_local.inverted() * foot.bone.matrix_local
    footmat = get_pose_matrix_in_other_space(toei.matrix, foot) * mat
    set_pose_rotation(foot, footmat)
    set_pose_scale(foot, footmat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def ik2fk_leg(obj, fk, ik):
    """ Matches the ik bones in a leg rig to the fk bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    thigh    = obj.pose.bones[fk[0]]
    shin     = obj.pose.bones[fk[1]]
    foot     = obj.pose.bones[fk[2]]
    toe      = obj.pose.bones[fk[3]]

    thighi   = obj.pose.bones[ik[0]]
    shini    = obj.pose.bones[ik[1]]
    footi    = obj.pose.bones[ik[2]]
    footroll = obj.pose.bones[ik[3]]
    mfooti   = obj.pose.bones[ik[4]]
    toei     = obj.pose.bones[ik[5]]
    
    # Clear footroll
    set_pose_rotation(footroll, Matrix())

    # Foot position
    mat = mfooti.bone.matrix_local.inverted() * footi.bone.matrix_local
    footmat = get_pose_matrix_in_other_space(foot.matrix, footi) * mat
    set_pose_translation(footi, footmat)
    set_pose_rotation(footi, footmat)
    set_pose_scale(footi, footmat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')

    # Toe position
    match_pose_translation(toei, toe)
    match_pose_rotation(toei, toe)
    match_pose_scale(toei, toe)

    # Thigh position
    match_pose_translation(thighi, thigh)
    match_pose_rotation(thighi, thigh)
    match_pose_scale(thighi, thigh)

    # Rotation Correction
    correct_rotation(thighi,thigh)


##############################
## IK/FK snapping operators ##
##############################

class Arm_FK2IK(bpy.types.Operator):
    """ Snaps an FK arm to an IK arm.
    """
    bl_idname = "pose.gamerig_arm_fk2ik_{rig_id}"
    bl_label = "Snap FK arm to IK"
    bl_options = {{'UNDO'}}

    uarm_fk = bpy.props.StringProperty(name="Upper Arm FK Name")
    farm_fk = bpy.props.StringProperty(name="Forerm FK Name")
    hand_fk = bpy.props.StringProperty(name="Hand FK Name")

    uarm_ik = bpy.props.StringProperty(name="Upper Arm IK Name")
    farm_ik = bpy.props.StringProperty(name="Forearm IK Name")
    hand_ik = bpy.props.StringProperty(name="Hand IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            fk2ik_arm(context.active_object, fk=[self.uarm_fk, self.farm_fk, self.hand_fk], ik=[self.uarm_ik, self.farm_ik, self.hand_ik])
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Arm_IK2FK(bpy.types.Operator):
    """ Snaps an IK arm to an FK arm.
    """
    bl_idname = "pose.gamerig_arm_ik2fk_{rig_id}"
    bl_label = "Snap IK arm to FK"
    bl_options = {{'UNDO'}}

    uarm_fk = bpy.props.StringProperty(name="Upper Arm FK Name")
    farm_fk = bpy.props.StringProperty(name="Forerm FK Name")
    hand_fk = bpy.props.StringProperty(name="Hand FK Name")

    uarm_ik = bpy.props.StringProperty(name="Upper Arm IK Name")
    farm_ik = bpy.props.StringProperty(name="Forearm IK Name")
    hand_ik = bpy.props.StringProperty(name="Hand IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            ik2fk_arm(context.active_object, fk=[self.uarm_fk, self.farm_fk, self.hand_fk], ik=[self.uarm_ik, self.farm_ik, self.hand_ik])
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Leg_FK2IK(bpy.types.Operator):
    """ Snaps an FK leg to an IK leg.
    """
    bl_idname = "pose.gamerig_leg_fk2ik_{rig_id}"
    bl_label = "Snap FK leg to IK"
    bl_options = {{'UNDO'}}

    thigh_fk = bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  = bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  = bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   = bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik = bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  = bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  = bpy.props.StringProperty(name="Foot IK Name")
    toe_ik   = bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            fk2ik_leg(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.foot_fk, self.toe_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.toe_ik])
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


class Leg_IK2FK(bpy.types.Operator):
    """ Snaps an IK leg to an FK leg.
    """
    bl_idname = "pose.gamerig_leg_ik2fk_{rig_id}"
    bl_label = "Snap IK leg to FK"
    bl_options = {{'UNDO'}}

    thigh_fk = bpy.props.StringProperty(name="Thigh FK Name")
    shin_fk  = bpy.props.StringProperty(name="Shin FK Name")
    foot_fk  = bpy.props.StringProperty(name="Foot FK Name")
    toe_fk   = bpy.props.StringProperty(name="Toe FK Name")

    thigh_ik = bpy.props.StringProperty(name="Thigh IK Name")
    shin_ik  = bpy.props.StringProperty(name="Shin IK Name")
    foot_ik  = bpy.props.StringProperty(name="Foot IK Name")
    footroll = bpy.props.StringProperty(name="Foot Roll Name")
    mfoot_ik = bpy.props.StringProperty(name="MFoot IK Name")
    toe_ik   = bpy.props.StringProperty(name="Toe IK Name")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'POSE'

    def execute(self, context):
        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            ik2fk_leg(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.foot_fk, self.toe_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.footroll, self.mfoot_ik, self.toe_ik])
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo
        return {{'FINISHED'}}


###################
## Rig UI Panels ##
###################

class PropertiesPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "GameRig Properties"
    bl_idname = "PT_gamerig_properties_{rig_id}"

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        try:
            return 'gamerig_layers' not in context.active_object.data and context.active_object.data.get("gamerig_id") == "{rig_id}"
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        pose_bones = context.active_object.pose.bones
        rig_id = "{rig_id}"
        try:
            selected_bones = [bone.name for bone in context.selected_pose_bones]
            if context.active_pose_bone and not context.active_pose_bone.name in selected_bones:
                selected_bones.append(context.active_pose_bone.name)
        except (AttributeError, TypeError):
            return

        def is_selected(names):
            # Returns whether any of the named bones are selected.
            if type(names) == list:
                for name in names:
                    if name in selected_bones:
                        return True
            elif names in selected_bones:
                return True
            return False        

{properties}


class LayersPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "GameRig Layers"
    bl_idname = "PT_gamerig_layers_{rig_id}"

    @classmethod
    def poll(self, context):
        try:
            return 'gamerig_layers' not in context.active_object.data and context.active_object.data.get("gamerig_id") == "{rig_id}"
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        col = layout.column()
{layers}

for cl in (Arm_FK2IK, Arm_IK2FK, Leg_FK2IK, Leg_IK2FK, PropertiesPanel, LayersPanel):
    register_class(cl)
'''
