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

import bpy
import imp
import importlib
import math
import random
import string
import time
import re
import os
from mathutils import Vector, Matrix, Color
from rna_prop_ui import rna_idprop_ui_prop_get

RIG_DIR = "rigs"  # Name of the directory where rig types are kept
METARIG_DIR = "metarigs"  # Name of the directory where metarigs are kept

ORG_PREFIX = "ORG-"  # Prefix of original bones.
JIG_PREFIX = "JIG-"  # Prefix of jig bones. (delete automatically after generation.)
MCH_PREFIX = "MCH-"  # Prefix of mechanism bones.

MODULE_NAME = "gamerig"  # Windows/Mac blender is weird, so __package__ doesn't work --- realy even now?

#=======================================================================
# Error handling
#=======================================================================
class MetarigError(Exception):
    """ Exception raised for errors.
    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


#=======================================================================
# Rig id generation
#=======================================================================

def random_id(length=10):
    """ Generates a random alphanumeric id string.
    """
    return ''.join([random.choice(string.ascii_lowercase + string.digits) for i in range(length)])
    #return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

#=======================================================================
# Name manipulation
#=======================================================================

def strip_trailing_number(s):
    m = re.search(r'\.(\d{3})$', s)
    return s[0:-4] if m else s


def unique_name(collection, base_name):
    base_name = strip_trailing_number(base_name)
    count = 1
    name = base_name

    while collection.get(name):
        name = "%s.%03d" % (base_name, count)
        count += 1
    return name


def basename(name):
    """ Returns the name with ORG_PREFIX stripped from it.
        """
    if name.startswith(ORG_PREFIX):
        return name[len(ORG_PREFIX):]
    elif name.startswith(JIG_PREFIX):
        return name[len(JIG_PREFIX):]
    elif name.startswith(MCH_PREFIX):
        return name[len(MCH_PREFIX):]
    else:
        return name


def is_org(name):
    return name.startswith(ORG_PREFIX) or name.startswith(JIG_PREFIX)


def is_jig(name):
    return name.startswith(JIG_PREFIX)


def is_mch(name):
    return name.startswith(MCH_PREFIX)


def org(name):
    """ Prepends the ORG_PREFIX to a name if it doesn't already have
        it, and returns it.
    """
    if is_org(name):
        return name
    else:
        return ORG_PREFIX + name


def mch(name):
    """ Prepends the MCH_PREFIX to a name if it doesn't already have
        it, and returns it.
    """
    if name.startswith(MCH_PREFIX):
        return name
    else:
        return MCH_PREFIX + name

make_mechanism_name = mch


def insert_before_first_period(name, text):
    t = name.split('.', 1)
    return t[0] + text + '.' + t[1] if len(t) > 1 else name + text

#=======================
# Bone manipulation
#=======================

def new_bone(obj, bone_name):
    """ Adds a new bone to the given armature object.
        Returns the resulting bone's name.
    """
    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        edit_bone = obj.data.edit_bones.new(bone_name)
        name = edit_bone.name
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 1, 0)
        edit_bone.roll = 0
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        return name
    else:
        raise MetarigError("Can't add new bone '%s' outside of edit mode" % bone_name)


def copy_bone_simple(obj, bone_name, assign_name=''):
    """ Makes a copy of the given bone in the given armature object.
        but only copies head, tail positions and roll. Does not
        address parenting either.
    """
    #if bone_name not in obj.data.bones:
    if bone_name not in obj.data.edit_bones:
        raise MetarigError("copy_bone(): bone '%s' not found, cannot copy it" % bone_name)

    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        if assign_name == '':
            assign_name = bone_name
        # Copy the edit bone
        edit_bone_1 = obj.data.edit_bones[bone_name]
        edit_bone_2 = obj.data.edit_bones.new(assign_name)
        bone_name_1 = bone_name
        bone_name_2 = edit_bone_2.name

        # Copy edit bone attributes
        edit_bone_2.layers = list(edit_bone_1.layers)

        edit_bone_2.head = Vector(edit_bone_1.head)
        edit_bone_2.tail = Vector(edit_bone_1.tail)
        edit_bone_2.roll = edit_bone_1.roll

        return bone_name_2
    else:
        raise MetarigError("Cannot copy bones outside of edit mode")


def copy_bone(obj, bone_name, assign_name=''):
    """ Makes a copy of the given bone in the given armature object.
        Returns the resulting bone's name.
    """
    #if bone_name not in obj.data.bones:
    if bone_name not in obj.data.edit_bones:
        raise MetarigError("copy_bone(): bone '%s' not found, cannot copy it" % bone_name)

    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        if assign_name == '':
            assign_name = bone_name
        # Copy the edit bone
        edit_bone_1 = obj.data.edit_bones[bone_name]
        edit_bone_2 = obj.data.edit_bones.new(assign_name)
        bone_name_1 = bone_name
        bone_name_2 = edit_bone_2.name

        edit_bone_2.parent = edit_bone_1.parent
        edit_bone_2.use_connect = edit_bone_1.use_connect

        # Copy edit bone attributes
        edit_bone_2.layers = list(edit_bone_1.layers)

        edit_bone_2.head = Vector(edit_bone_1.head)
        edit_bone_2.tail = Vector(edit_bone_1.tail)
        edit_bone_2.roll = edit_bone_1.roll

        edit_bone_2.use_inherit_rotation = edit_bone_1.use_inherit_rotation
        edit_bone_2.use_inherit_scale = edit_bone_1.use_inherit_scale
        edit_bone_2.use_local_location = edit_bone_1.use_local_location

        edit_bone_2.use_deform = edit_bone_1.use_deform
        edit_bone_2.bbone_segments = edit_bone_1.bbone_segments
        if hasattr(edit_bone_1, 'bbone_in'):
            edit_bone_2.bbone_in = edit_bone_1.bbone_in
            edit_bone_2.bbone_out = edit_bone_1.bbone_out
        else:
            edit_bone_2.bbone_easein = edit_bone_1.bbone_easein
            edit_bone_2.bbone_easeout = edit_bone_1.bbone_easeout

        bpy.ops.object.mode_set(mode='OBJECT')

        # Get the pose bones
        pose_bone_1 = obj.pose.bones[bone_name_1]
        pose_bone_2 = obj.pose.bones[bone_name_2]

        # Copy pose bone attributes
        pose_bone_2.rotation_mode = pose_bone_1.rotation_mode
        pose_bone_2.rotation_axis_angle = tuple(pose_bone_1.rotation_axis_angle)
        pose_bone_2.rotation_euler = tuple(pose_bone_1.rotation_euler)
        pose_bone_2.rotation_quaternion = tuple(pose_bone_1.rotation_quaternion)

        pose_bone_2.lock_location = tuple(pose_bone_1.lock_location)
        pose_bone_2.lock_scale = tuple(pose_bone_1.lock_scale)
        pose_bone_2.lock_rotation = tuple(pose_bone_1.lock_rotation)
        pose_bone_2.lock_rotation_w = pose_bone_1.lock_rotation_w
        pose_bone_2.lock_rotations_4d = pose_bone_1.lock_rotations_4d

        # Copy custom properties
        for key in pose_bone_1.keys():
            if key != "_RNA_UI" and key != "gamerig_parameters" and key != "gamerig_type":
                prop1 = rna_idprop_ui_prop_get(pose_bone_1, key, create=False)
                if prop1 is not None:
                    prop2 = rna_idprop_ui_prop_get(pose_bone_2, key, create=True)
                    pose_bone_2[key] = pose_bone_1[key]
                    for key in prop1.keys():
                        prop2[key] = prop1[key]

        bpy.ops.object.mode_set(mode='EDIT')

        return bone_name_2
    else:
        raise MetarigError("Cannot copy bones outside of edit mode")


def flip_bone(obj, bone_name):
    """ Flips an edit bone.
    """
    if bone_name not in obj.data.bones:
        raise MetarigError("flip_bone(): bone '%s' not found, cannot copy it" % bone_name)

    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        bone = obj.data.edit_bones[bone_name]
        head = Vector(bone.head)
        tail = Vector(bone.tail)
        bone.tail = head + tail
        bone.head = tail
        bone.tail = head
    else:
        raise MetarigError("Cannot flip bones outside of edit mode")


def put_bone(obj, bone_name, pos):
    """ Places a bone at the given position.
    """
    if bone_name not in obj.data.bones:
        raise MetarigError("put_bone(): bone '%s' not found, cannot move it" % bone_name)

    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        bone = obj.data.edit_bones[bone_name]

        delta = pos - bone.head
        bone.translate(delta)
    else:
        raise MetarigError("Cannot 'put' bones outside of edit mode")

#=============================================
# Widget creation
#=============================================

def get_wgt_name(rig_name, bone_name):
    """ Object's with name widget_<rig_name>_<bone_name> get used as that bone's shape.
    """
    return 'widget_%s_%s' % (rig_name, bone_name)


def obj_to_bone(obj, rig, bone_name):
    """ Places an object at the location/rotation/scale of the given bone.
    """
    if bpy.context.mode == 'EDIT_ARMATURE':
        raise MetarigError("obj_to_bone(): does not work while in edit mode")

    bone = rig.data.bones[bone_name]

    mat = rig.matrix_world * bone.matrix_local

    obj.location = mat.to_translation()

    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = mat.to_euler()

    scl = mat.to_scale()
    scl_avg = (scl[0] + scl[1] + scl[2]) / 3
    obj.scale = (bone.length * scl_avg), (bone.length * scl_avg), (bone.length * scl_avg)


def create_widget(rig, bone_name, bone_transform_name=None):
    """ Creates an empty widget object for a bone, and returns the object.
    """
    if bone_transform_name is None:
        bone_transform_name = bone_name

    obj_name = get_wgt_name(rig.name, bone_name)
    scene = bpy.context.scene
    id_store = bpy.context.window_manager

    # Check if it already exists in the scene
    if obj_name in scene.objects:
        # Move object to bone position, in case it changed
        obj = scene.objects[obj_name]
        obj_to_bone(obj, rig, bone_transform_name)

        return None
    else:
        # Delete object if it exists in blend data but not scene data.
        # This is necessary so we can then create the object without
        # name conflicts.
        if obj_name in bpy.data.objects:
            bpy.data.objects[obj_name].user_clear()
            bpy.data.objects.remove(bpy.data.objects[obj_name])

        # Create mesh object
        mesh = bpy.data.meshes.new(obj_name)
        obj = bpy.data.objects.new(obj_name, mesh)
        scene.objects.link(obj)
        if not hasattr(create_widget, 'created_widgets') or create_widget.created_widgets is None:
            create_widget.created_widgets = []
        create_widget.created_widgets.append((obj, bone_name))

        # Move object to bone position and set layers
        obj_to_bone(obj, rig, bone_transform_name)

        return obj


def assign_and_unlink_all_widgets(scene, armature):
    """ Unlink all created widget objects from current scene for cleanup.
    """
    if hasattr(create_widget, 'created_widgets') and create_widget.created_widgets is not None:
        for obj, bone_name in create_widget.created_widgets:
            armature.pose.bones[bone_name].custom_shape = obj
            scene.objects.unlink(obj)
        create_widget.created_widgets = None


#=============================================
# Math
#=============================================

def angle_on_plane(plane, vec1, vec2):
    """ Return the angle between two vectors projected onto a plane.
    """
    plane.normalize()
    vec1 = vec1 - (plane * (vec1.dot(plane)))
    vec2 = vec2 - (plane * (vec2.dot(plane)))
    vec1.normalize()
    vec2.normalize()

    # Determine the angle
    angle = math.acos(max(-1.0, min(1.0, vec1.dot(vec2))))

    if angle < 0.00001:  # close enough to zero that sign doesn't matter
        return angle

    # Determine the sign of the angle
    vec3 = vec2.cross(vec1)
    vec3.normalize()
    sign = vec3.dot(plane)
    if sign >= 0:
        sign = 1
    else:
        sign = -1

    return angle * sign


def align_bone_roll(obj, bone1, bone2):
    """ Aligns the roll of two bones.
    """
    bone1_e = obj.data.edit_bones[bone1]
    bone2_e = obj.data.edit_bones[bone2]

    bone1_e.roll = 0.0

    # Get the directions the bones are pointing in, as vectors
    y1 = bone1_e.y_axis
    x1 = bone1_e.x_axis
    y2 = bone2_e.y_axis
    x2 = bone2_e.x_axis

    # Get the shortest axis to rotate bone1 on to point in the same direction as bone2
    axis = y1.cross(y2)
    axis.normalize()

    # Angle to rotate on that shortest axis
    angle = y1.angle(y2)

    # Create rotation matrix to make bone1 point in the same direction as bone2
    rot_mat = Matrix.Rotation(angle, 3, axis)

    # Roll factor
    x3 = rot_mat * x1
    dot = x2 * x3
    if dot > 1.0:
        dot = 1.0
    elif dot < -1.0:
        dot = -1.0
    roll = math.acos(dot)

    # Set the roll
    bone1_e.roll = roll

    # Check if we rolled in the right direction
    x3 = rot_mat * bone1_e.x_axis
    check = x2 * x3

    # If not, reverse
    if check < 0.9999:
        bone1_e.roll = -roll


def align_bone_x_axis(obj, bone, vec):
    """ Rolls the bone to align its x-axis as closely as possible to
        the given vector.
        Must be in edit mode.
    """
    bone_e = obj.data.edit_bones[bone]

    vec = vec.cross(bone_e.y_axis)
    vec.normalize()

    dot = max(-1.0, min(1.0, bone_e.z_axis.dot(vec)))
    angle = math.acos(dot)

    bone_e.roll += angle

    dot1 = bone_e.z_axis.dot(vec)

    bone_e.roll -= angle * 2

    dot2 = bone_e.z_axis.dot(vec)

    if dot1 > dot2:
        bone_e.roll += angle * 2


def align_bone_z_axis(obj, bone, vec):
    """ Rolls the bone to align its z-axis as closely as possible to
        the given vector.
        Must be in edit mode.
    """
    bone_e = obj.data.edit_bones[bone]

    vec = bone_e.y_axis.cross(vec)
    vec.normalize()

    dot = max(-1.0, min(1.0, bone_e.x_axis.dot(vec)))
    angle = math.acos(dot)

    bone_e.roll += angle

    dot1 = bone_e.x_axis.dot(vec)

    bone_e.roll -= angle * 2

    dot2 = bone_e.x_axis.dot(vec)

    if dot1 > dot2:
        bone_e.roll += angle * 2


def align_bone_y_axis(obj, bone, vec):
    """ Matches the bone y-axis to
        the given vector.
        Must be in edit mode.
    """

    bone_e = obj.data.edit_bones[bone]
    vec.normalize()
    vec = vec * bone_e.length

    bone_e.tail = bone_e.head + vec


#=============================================
# Misc
#=============================================

def copy_attributes(a, b):
    keys = dir(a)
    for key in keys:
        if not key.startswith("_") \
        and not key.startswith("error_") \
        and key != "group" \
        and key != "is_valid" \
        and key != "rna_type" \
        and key != "bl_rna":
            try:
                setattr(b, key, getattr(a, key))
            except AttributeError:
                pass


def get_rig_type(rig_type):
    """ Fetches a rig module by name, and returns it.
    """
    name = ".%s.%s" % (RIG_DIR, rig_type)
    submod = importlib.import_module(name, package=MODULE_NAME)
    importlib.reload(submod)
    return submod


def get_metarig_module(metarig_name, path=METARIG_DIR):
    """ Fetches a rig module by name, and returns it.
    """

    name = ".%s.%s" % (path, metarig_name)
    submod = importlib.import_module(name, package=MODULE_NAME)
    importlib.reload(submod)
    return submod


def connected_children_names(obj, bone_name):
    """ Returns a list of bone names (in order) of the bones that form a single
        connected chain starting with the given bone as a parent.
        If there is a connected branch, the list stops there.
    """
    bone = obj.data.bones[bone_name]
    names = []

    while True:
        connects = 0
        con_name = ""

        for child in bone.children:
            if child.use_connect:
                connects += 1
                con_name = child.name

        if connects == 1:
            names.append(con_name)
            bone = obj.data.bones[con_name]
        else:
            break

    return names

def find_root_bone(obj, bone_name):
    """ Find root rig original bone from all parent.
        This works while initializing (inner rig's __init__ function) only.
    """
    bone = obj.data.edit_bones[bone_name]
    if bone:
        bone = bone.parent
        while(bone):
            pb = obj.pose.bones[bone.name]
            if hasattr(pb, 'gamerig_type') and pb.gamerig_type == 'root':
                return bone.name
            bone = bone.parent
    return None

def has_connected_children(bone):
    """ Returns true/false whether a bone has connected children or not.
    """
    t = False
    for b in bone.children:
        t = t or b.use_connect
    return t


def get_layers(layers):
    """ Does it's best to exctract a set of layers from any data thrown at it.
    """
    if type(layers) == int:
        return [x == layers for x in range(0, 32)]
    elif type(layers) == str:
        s = layers.split(",")
        l = []
        for i in s:
            try:
                l.append(int(float(i)))
            except ValueError:
                pass
        return [x in l for x in range(0, 32)]
    elif type(layers) == tuple or type(layers) == list:
        return [x in layers for x in range(0, 32)]
    else:
        try:
            list(layers)
        except TypeError:
            pass
        else:
            return [x in layers for x in range(0, 32)]


def write_metarig(obj, func_name="create", layers=False, groups=False, template=False):
    """
    Write a metarig as a python script, this rig is to have all info needed for
    generating the real rig with gamerig.
    """
    code = []

    code.append("import bpy\n\n")
    code.append("from mathutils import Color\n\n")

    code.append("def %s(obj):" % func_name)
    code.append("    # generated by gamerig.utils.write_metarig")
    bpy.ops.object.mode_set(mode='EDIT')
    code.append("    bpy.ops.object.mode_set(mode='EDIT')")
    code.append("    arm = obj.data")

    arm = obj.data

    if template:
        if arm.gamerig_rig_ui_template:
            code.append("\n    arm.gamerig_rig_ui_template = '%s'" % arm.gamerig_rig_ui_template)
        else:
            code.append("\n    arm.gamerig_rig_ui_template = 'ui_template'")

    # GameRig bone group colors info
    if groups and len(arm.gamerig_colors) > 0:
        code.append("\n    for i in range(" + str(len(arm.gamerig_colors)) + "):")
        code.append("        arm.gamerig_colors.add()\n")

        for i in range(len(arm.gamerig_colors)):
            name = arm.gamerig_colors[i].name
            active = arm.gamerig_colors[i].active
            normal = arm.gamerig_colors[i].normal
            select = arm.gamerig_colors[i].select
            standard_colors_lock = arm.gamerig_colors[i].standard_colors_lock
            code.append('    arm.gamerig_colors[' + str(i) + '].name = "' + name + '"')
            code.append('    arm.gamerig_colors[' + str(i) + '].active = Color(' + str(active[:]) + ')')
            code.append('    arm.gamerig_colors[' + str(i) + '].normal = Color(' + str(normal[:]) + ')')
            code.append('    arm.gamerig_colors[' + str(i) + '].select = Color(' + str(select[:]) + ')')
            code.append('    arm.gamerig_colors[' + str(i) + '].standard_colors_lock = ' + str(standard_colors_lock))

    # GameRig layer layout info
    if layers and len(arm.gamerig_layers) > 0:
        code.append("\n    for i in range(" + str(len(arm.gamerig_layers)) + "):")
        code.append("        arm.gamerig_layers.add()\n")

        for i in range(len(arm.gamerig_layers)):
            name = arm.gamerig_layers[i].name
            row = arm.gamerig_layers[i].row
            set = arm.gamerig_layers[i].selset
            group = arm.gamerig_layers[i].group
            code.append('    arm.gamerig_layers[' + str(i) + '].name = "' + name + '"')
            code.append('    arm.gamerig_layers[' + str(i) + '].row = ' + str(row))
            code.append('    arm.gamerig_layers[' + str(i) + '].selset = ' + str(set))
            code.append('    arm.gamerig_layers[' + str(i) + '].group = ' + str(group))

    # write parents first
    bones = [(len(bone.parent_recursive), bone.name) for bone in arm.edit_bones]
    bones.sort(key=lambda item: item[0])
    bones = [item[1] for item in bones]

    code.append("\n    bones = {}\n")

    for bone_name in bones:
        bone = arm.edit_bones[bone_name]
        code.append("    bone = arm.edit_bones.new(%r)" % bone.name)
        code.append("    bone.head[:] = %.4f, %.4f, %.4f" % bone.head.to_tuple(4))
        code.append("    bone.tail[:] = %.4f, %.4f, %.4f" % bone.tail.to_tuple(4))
        code.append("    bone.roll = %.4f" % bone.roll)
        code.append("    bone.use_connect = %s" % str(bone.use_connect))
        code.append("    bone.use_deform = %s" % str(bone.use_deform))
        if bone.parent:
            code.append("    bone.parent = arm.edit_bones[bones[%r]]" % bone.parent.name)
        code.append("    bones[%r] = bone.name" % bone.name)

    bpy.ops.object.mode_set(mode='OBJECT')
    code.append("")
    code.append("    bpy.ops.object.mode_set(mode='OBJECT')")

    # Rig type and other pose properties
    for bone_name in bones:
        pbone = obj.pose.bones[bone_name]

        code.append("    pbone = obj.pose.bones[bones[%r]]" % bone_name)
        code.append("    pbone.gamerig_type = %r" % pbone.gamerig_type)
        code.append("    pbone.lock_location = %s" % str(tuple(pbone.lock_location)))
        code.append("    pbone.lock_rotation = %s" % str(tuple(pbone.lock_rotation)))
        code.append("    pbone.lock_rotation_w = %s" % str(pbone.lock_rotation_w))
        code.append("    pbone.lock_scale = %s" % str(tuple(pbone.lock_scale)))
        code.append("    pbone.rotation_mode = %r" % pbone.rotation_mode)
        if layers:
            code.append("    pbone.bone.layers = %s" % str(list(pbone.bone.layers)))
        # Rig type parameters
        for param_name in pbone.gamerig_parameters.keys():
            param = getattr(pbone.gamerig_parameters, param_name, '')
            if str(type(param)) == "<class 'bpy_prop_array'>":
                param = list(param)
            if type(param) == str:
                param = '"' + param + '"'
            code.append("    try:")
            code.append("        pbone.gamerig_parameters.%s = %s" % (param_name, str(param)))
            code.append("    except AttributeError:")
            code.append("        pass")

    code.append("\n    bpy.ops.object.mode_set(mode='EDIT')")
    code.append("    for bone in arm.edit_bones:")
    code.append("        bone.select = False")
    code.append("        bone.select_head = False")
    code.append("        bone.select_tail = False")

    code.append("    for b in bones:")
    code.append("        bone = arm.edit_bones[bones[b]]")
    code.append("        bone.select = True")
    code.append("        bone.select_head = True")
    code.append("        bone.select_tail = True")
    code.append("        arm.edit_bones.active = bone")

    # Set appropriate layers visible
    if layers:
        # Find what layers have bones on them
        active_layers = []
        for bone_name in bones:
            bone = obj.data.bones[bone_name]
            for i in range(len(bone.layers)):
                if bone.layers[i]:
                    if i not in active_layers:
                        active_layers.append(i)
        active_layers.sort()

        code.append("\n    arm.layers = [(x in " + str(active_layers) + ") for x in range(" + str(len(arm.layers)) + ")]")

    code.append('\nif __name__ == "__main__":')
    code.append("    " + func_name + "(bpy.context.active_object)\n")

    return "\n".join(code)


def write_widget(obj):
    """ Write a mesh object as a python script for widget use.
    """
    script = ""
    script += "def create_thing_widget(rig, bone_name, size=1.0, bone_transform_name=None):\n"
    script += "    obj = create_widget(rig, bone_name, bone_transform_name)\n"
    script += "    if obj != None:\n"

    # Vertices
    if len(obj.data.vertices) > 0:
        script += "        verts = ["
        for v in obj.data.vertices:
            script += "({:.5}*size, {:.5}*size, {:.5}*size), ".format(
                v.co[0] if abs(v.co[0]) > 0.0001 else 0.0,
                v.co[1] if abs(v.co[1]) > 0.0001 else 0.0,
                v.co[2] if abs(v.co[2]) > 0.0001 else 0.0,
            )
        script += "]\n"
    else:
        script += "        verts = []\n"

    # Edges
    if len(obj.data.edges) > 0:
        script += "        edges = ["
        for e in obj.data.edges:
            script += "(" + str(e.vertices[0]) + ", " + str(e.vertices[1]) + "), "
        script += "]\n"
    else:
        script += "        edges = []\n"

    # Faces
    if len(obj.data.polygons) > 0:
        script += "        faces = ["
        for f in obj.data.polygons:
            script += "("
            for v in f.vertices:
                script += str(v) + ", "
            script += "), "
        script += "]\n"
    else:
        script += "        faces = []\n"

    # Build mesh
    script += "\n        mesh = obj.data\n"
    script += "        mesh.from_pydata(verts, edges, faces)\n"
    script += "        mesh.update()\n"
    script += "        return obj\n"
    script += "    else:\n"
    script += "        return None\n"

    return script


#=============================================
# Color correction functions
#=============================================

def linsrgb_to_srgb(linsrgb):
    """Convert physically linear RGB values into sRGB ones. The transform is
    uniform in the components, so *linsrgb* can be of any shape.

    *linsrgb* values should range between 0 and 1, inclusively.

    """
    # From Wikipedia, but easy analogue to the above.
    gamma = 1.055 * linsrgb**(1./2.4) - 0.055
    scale = linsrgb * 12.92
    # return np.where (linsrgb > 0.0031308, gamma, scale)
    if linsrgb > 0.0031308:
        return gamma
    return scale


def gamma_correct(color):
    corrected_color = Color()
    for i, component in enumerate(color):
        corrected_color[i] = linsrgb_to_srgb(color[i])
    return corrected_color


#=============================================
# Keyframing functions
#=============================================


def get_keyed_frames(rig):
    frames = []
    if rig.animation_data:
        if rig.animation_data.action:
            fcus = rig.animation_data.action.fcurves
            for fc in fcus:
                for kp in fc.keyframe_points:
                    if kp.co[0] not in frames:
                        frames.append(kp.co[0])

    frames.sort()

    return frames


def bones_in_frame(f, rig, *args):
    """
    True if one of the bones listed in args is animated at frame f
    :param f: the frame
    :param rig: the rig
    :param args: bone names
    :return:
    """

    if rig.animation_data and rig.animation_data.action:
        fcus = rig.animation_data.action.fcurves
    else:
        return False

    for fc in fcus:
        animated_frames = [kp.co[0] for kp in fc.keyframe_points]
        for bone in args:
            if bone in fc.data_path.split('"') and f in animated_frames:
                return True

    return False


def overwrite_prop_animation(rig, bone, prop_name, value, frames):
    act = rig.animation_data.action
    if not act:
        return

    bone_name = bone.name
    curve = None

    for fcu in act.fcurves:
        words = fcu.data_path.split('"')
        if words[0] == "pose.bones[" and words[1] == bone_name and words[-2] == prop_name:
            curve = fcu
            break

    if not curve:
        return

    for kp in curve.keyframe_points:
        if kp.co[0] in frames:
            kp.co[1] = value
