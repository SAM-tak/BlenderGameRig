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


###########################
## Rig specify operators ##
###########################

{rigextras}
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

for cl in (PropertiesPanel, LayersPanel):
    register_class(cl)
'''
