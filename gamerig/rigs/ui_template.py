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
from math import acos, pi, radians, floor

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
    smat = rest_inv @ (par_rest @ (par_inv @ mat))

    # Compensate for non-local location
    #if not pose_bone.bone.use_local_location:
    #    loc = smat.to_translation() @ (par_rest.inverted() @ rest).to_quaternion()
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

        q = (par_rest.inverted() @ rest).to_quaternion()
        pose_bone.location = q @ loc


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
    set_pose_scale(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def insert_keyframe_by_mode(context, pb):
    option = {{'INSERTKEY_AVAILABLE'}} if context.scene.tool_settings.use_keyframe_insert_auto else {{'INSERTKEY_REPLACE'}}
    pb.keyframe_insert(data_path='location', group='Bone', options=option)
    pb.keyframe_insert(data_path='scale', group='Bone', options=option)
    if pb.rotation_mode == 'QUATERNION':
        pb.keyframe_insert(data_path='rotation_quaternion', group='Bone', options=option)
    elif pb.rotation_mode == 'AXIS_ANGLE':
        pb.keyframe_insert(data_path='rotation_axis_angle', group='Bone', options=option)
    else:
        pb.keyframe_insert(data_path='rotation_euler', group='Bone', options=option)


def match_pole_direction(context, pb_ik_pole, pb_fk_chain1, pb_fk_chain2, pb_fk_chain3):
    if pb_ik_pole.lock_rotation[0]:
        # X axis limb, Z axis pole rot
        # Reset pole vector
        prev = pb_ik_pole.rotation_euler.z
        pb_ik_pole.rotation_euler.z = 0
        context.view_layer.update()
        x = Vector((pb_ik_pole.matrix[0][0], pb_ik_pole.matrix[1][0], pb_ik_pole.matrix[2][0])).normalized()
        y = (pb_fk_chain3.matrix.to_translation() - pb_fk_chain1.matrix.to_translation()).normalized()
        z = x.cross(y)
        # Make inverted IK space rotation matrix
        mi = Matrix(((x[0],y[0],z[0]),(x[1],y[1],z[1]),(x[2],y[2],z[2]))).inverted()
        x2 = mi @ (pb_fk_chain2.matrix.to_translation() - pb_fk_chain1.matrix.to_translation()).normalized().cross(y)
        pb_ik_pole.rotation_euler.z = Vector((1, 0)).angle_signed(Vector((x2[0], x2[2])), prev)
    else:
        # Z axis limb, X axis pole rot
        # Reset pole vector
        prev = pb_ik_pole.rotation_euler.x
        pb_ik_pole.rotation_euler.x = 0
        context.view_layer.update()
        z = Vector((pb_ik_pole.matrix[0][2], pb_ik_pole.matrix[1][2], pb_ik_pole.matrix[2][2])).normalized()
        y = (pb_fk_chain3.matrix.to_translation() - pb_fk_chain1.matrix.to_translation()).normalized()
        x = y.cross(z)
        # Make inverted IK space rotation matrix
        mi = Matrix(((x[0],y[0],z[0]),(x[1],y[1],z[1]),(x[2],y[2],z[2]))).inverted()
        z2 = mi @ (pb_fk_chain2.matrix.to_translation() - pb_fk_chain1.matrix.to_translation()).normalized().cross(y)
        pb_ik_pole.rotation_euler.x = Vector((1, 0)).angle_signed(Vector((z2[0], z2[1])), prev)

classes = []

###########################
## Rig special operators ##
###########################
{operators}
###################
## Rig UI Panels ##
###################

class PropertiesPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Item'
    bl_label = 'GameRig Properties'
    bl_idname = 'GAMERIG_PT_properties_{rig_id}'

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        try:
            return context.object.data['gamerig_id'] == '{rig_id}'
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        pose_bones = context.object.pose.bones
        rig_id = '{rig_id}'
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

classes.append(PropertiesPanel)

class BoneCollectionsPanel(bpy.types.Panel):
    bl_idname = 'GAMERIG_PT_bone_collections_{rig_id}'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_label = 'GameRig Bone Collections'

    @classmethod
    def poll(cls, context):
        try:
            return context.object and context.object.type == 'ARMATURE' and context.object.data['gamerig_id'] == '{rig_id}'
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        col = layout.column()
{bone_collections}

classes.append(BoneCollectionsPanel)

register, unregister = bpy.utils.register_classes_factory(classes)

if __name__ == "__main__":
    register()
'''
