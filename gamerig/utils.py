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

CTRL_PREFIX = "c."   # Prefix of controller bones.
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
# Rig name generation
#=======================================================================

def get_rig_name(metarig):
    rig_name = metarig.data.gamerig.rig_name
    if not rig_name:
        rig_name = metarig.name
        if 'metarig' in rig_name:
            rig_name = rig_name.replace('metarig', 'rig')
        else:
            rig_name = rig_name + 'rig'
        rig_name = unique_name(bpy.data.objects.keys(), rig_name)
    return rig_name


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

    while name in collection:
        name = "%s.%03d" % (base_name, count)
        count += 1
    return name


def basename(name):
    """ Returns the name with CTRL_PREFIX or MCH_PREFIX stripped from it.
        """
    if name.startswith(CTRL_PREFIX):
        return name[len(CTRL_PREFIX):]
    elif name.startswith(MCH_PREFIX):
        return name[len(MCH_PREFIX):]
    else:
        return name


def is_org(name):
    return not name.startswith(CTRL_PREFIX) and not name.startswith(MCH_PREFIX)


def is_ctrl(name):
    return name.startswith(CTRL_PREFIX)


def is_jig(name):
    return name.startswith(JIG_PREFIX)


def is_mch(name):
    return name.startswith(MCH_PREFIX)


def ctrlname(name):
    """ Prepends the CTRL_PREFIX to a name if it doesn't already have
        it, and returns it.
    """
    if name:
        if name.startswith(CTRL_PREFIX):
            return name
        else:
            return CTRL_PREFIX + name


def mchname(name):
    """ Prepends the MCH_PREFIX to a name if it doesn't already have
        it, and returns it.
    """
    if name.startswith(MCH_PREFIX):
        return name
    else:
        return MCH_PREFIX + name


def insert_before_first_period(name, text):
    t = name.split('.', 1)
    return t[0] + text + '.' + t[1] if len(t) > 1 else name + text


#=======================
# Progress Handler
#=======================

progress = [0, 0]

def begin_progress(max):
    progress = (0, max)
    bpy.context.window_manager.progress_begin(progress[0], progress[1])
    bpy.context.window_manager.gamerig.progress_indicator = 0

def update_progress():
    progress[0] += 1
    bpy.context.window_manager.progress_update(progress[0])
    if progress[1] > 0:
        bpy.context.window_manager.gamerig.progress_indicator = progress[0] / progress[1] * 100

def end_progress():
    bpy.context.window_manager.progress_end()
    bpy.context.window_manager.gamerig.progress_indicator = -1

#=======================
# Bone manipulation
#=======================

def copy_bone(obj, bone_name, assign_name=''):
    """ Makes a copy of the given bone in the given armature object.
        Returns the resulting bone's name.
    """
    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        
        if bone_name not in obj.data.edit_bones:
            raise RuntimeError("copy_bone(): bone '%s' not found, cannot copy it" % bone_name)

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
        edit_bone_2.bbone_easein = edit_bone_1.bbone_easein
        edit_bone_2.bbone_easeout = edit_bone_1.bbone_easeout

        return bone_name_2
    else:
        raise RuntimeError("Cannot copy bones outside of edit mode")


def flip_bone(obj, bone_name):
    """ Flips an edit bone.
    """
    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        if bone_name not in obj.data.edit_bones:
            raise RuntimeError("flip_bone(): bone '%s' not found, cannot momve it" % bone_name)

        bone = obj.data.edit_bones[bone_name]
        head = Vector(bone.head)
        tail = Vector(bone.tail)
        bone.tail = head + tail
        bone.head = tail
        bone.tail = head
    else:
        raise RuntimeError("Cannot flip bones outside of edit mode")


def put_bone(obj, bone_name, pos):
    """ Places a bone at the given position.
    """
    if obj == bpy.context.active_object and bpy.context.mode == 'EDIT_ARMATURE':
        if bone_name not in obj.data.edit_bones:
            raise RuntimeError("put_bone(): bone '%s' not found, cannot move it" % bone_name)

        bone = obj.data.edit_bones[bone_name]

        delta = pos - bone.head
        bone.translate(delta)
    else:
        raise RuntimeError("Cannot 'put' bones outside of edit mode")

#=============================================
# Widget creation
#=============================================
def obj_to_bone(obj, rig, bone_name):
    """ Places an object at the location/rotation/scale of the given bone.
    """
    if bpy.context.mode == 'EDIT_ARMATURE':
        raise RuntimeError("obj_to_bone(): does not work while in edit mode")

    bone = rig.data.bones[bone_name]

    mat = rig.matrix_world @ bone.matrix_local

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

    widget_collection_name = rig.name + ' widgets'

    if widget_collection_name in bpy.data.collections:
        collection = bpy.data.collections[widget_collection_name]
    else:
        collection = bpy.data.collections.new(widget_collection_name)
        bpy.context.scene.collection.children.link(collection)
        bpy.context.view_layer.layer_collection.children[collection.name].hide_viewport = True
        collection.hide_render = True

    if not hasattr(create_widget, 'created_widgets'):
        create_widget.created_widgets = {}

    obj_name = 'widget_%s.%s' % (rig.name, basename(bone_name))

    # Check if it already exists in the collection
    if obj_name in collection.objects:
        # Move object to bone position, in case it changed
        obj = collection.objects[obj_name]
        obj_to_bone(obj, rig, bone_transform_name)
        create_widget.created_widgets[bone_name] = obj

        return None
    else:
        # Delete object if it exists in blend data but not scene data.
        # This is necessary so we can then create the object without
        # name conflicts.
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            obj.user_clear()
            bpy.data.objects.remove(obj)

        # Create mesh object
        mesh = bpy.data.meshes.new(obj_name)
        obj = bpy.data.objects.new(obj_name, mesh)
        collection.objects.link(obj)

        # Move object to bone position and set layers
        obj_to_bone(obj, rig, bone_transform_name)

        create_widget.created_widgets[bone_name] = obj

        return obj


def assign_all_widgets(armature):
    """ Assign all created widget objects for corresponding bones.
    """
    if hasattr(create_widget, 'created_widgets'):
        for bone_name, obj in create_widget.created_widgets.items():
            armature.pose.bones[bone_name].custom_shape = obj
        del create_widget.created_widgets


#=============================================
# Misc
#=============================================

def copy_attributes(a, b):
    keys = dir(a)
    for key in keys:
        if not key.startswith("_") \
        and not key.startswith("error_") \
        and key != "group" \
        and key != "strips" \
        and key != "is_valid" \
        and key != "rna_type" \
        and key != "bl_rna":
            try:
                setattr(b, key, getattr(a, key))
            except AttributeError:
                pass


def bone_props_ui_string(obj, bone_name):
    bone = obj.pose.bones[bone_name]
    rna_properties = {prop.identifier for prop in bone.bl_rna.properties if prop.is_runtime}
    ret = ""
    for k in bone.keys():
        if k == '_RNA_UI' or k in rna_properties:
            continue
        if isinstance(bone[k], float):
            ret += f"    layout.prop( pose_bones['{bone.name}'], '[\"{k}\"]', text='{k} ({bone.name})', slider = True )\n"

    if len(ret) > 0:
        return ret
    
    return None


def rig_module_name(rig_type):
    """ return a rig module name.
    """
    return ".%s.%s" % (RIG_DIR, rig_type)


def get_rig_type(rig_type):
    """ Fetches a rig module by name, and returns it.
    """
    submod = importlib.import_module(rig_module_name(rig_type), package=MODULE_NAME)
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


def children_names(obj, bone_name, depth):
    bone = obj.data.bones[bone_name]
    names = []

    for i in range(depth):
        connects = 0
        con_name = ""

        if len(bone.children) > 0:
            names.append(bone.children[0].name)
            bone = bone.children[0]
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
            if hasattr(pb, 'gamerig') and pb.gamerig.name == 'root':
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
    """ Does it's best to extract a set of layers from any data thrown at it.
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


def write_metarig(obj, func_name="create", metarig=False):
    """
    Write a metarig as a python script, this rig is to have all info needed for
    generating the real rig with gamerig.
    """
    code = []

    code.append("import bpy\n\n")
    if metarig:
        code.append("from mathutils import Color\n\n")

    code.append("def %s(obj):" % func_name)
    code.append("    # generated by gamerig.utils.write_metarig\n")

    if metarig:
        code.append("    obj.rotation_mode     = %r" % obj.rotation_mode)
        code.append("    obj.rotation_euler      = %s" % str(tuple(obj.rotation_euler)))
        code.append("    obj.rotation_quaternion = %s" % str(tuple(obj.rotation_quaternion)))
        code.append("    obj.rotation_axis_angle = %s\n" % str(tuple(obj.rotation_axis_angle)))

    bpy.ops.object.mode_set(mode='EDIT')
    code.append("    bpy.ops.object.mode_set(mode='EDIT')")
    code.append("    arm = obj.data")

    arm = obj.data

    if metarig:
        if arm.gamerig.rig_ui_template:
            code.append("\n    arm.gamerig.rig_ui_template = '%s'" % arm.gamerig.rig_ui_template)
        else:
            code.append("\n    arm.gamerig.rig_ui_template = 'ui_template'")

    # GameRig bone group colors info
    if metarig and len(arm.gamerig.colors) > 0:
        code.append("\n    for i in range(" + str(len(arm.gamerig.colors)) + "):")
        code.append("        arm.gamerig.colors.add()\n")

        for i in range(len(arm.gamerig.colors)):
            name = arm.gamerig.colors[i].name
            active = arm.gamerig.colors[i].active
            normal = arm.gamerig.colors[i].normal
            select = arm.gamerig.colors[i].select
            standard_colors_lock = arm.gamerig.colors[i].standard_colors_lock
            code.append('    arm.gamerig.colors[' + str(i) + '].name = "' + name + '"')
            code.append('    arm.gamerig.colors[' + str(i) + '].active = Color(' + str(active[:]) + ')')
            code.append('    arm.gamerig.colors[' + str(i) + '].normal = Color(' + str(normal[:]) + ')')
            code.append('    arm.gamerig.colors[' + str(i) + '].select = Color(' + str(select[:]) + ')')
            code.append('    arm.gamerig.colors[' + str(i) + '].standard_colors_lock = ' + str(standard_colors_lock))

    # GameRig layer layout info
    if metarig and len(arm.gamerig.layers) > 0:
        code.append("\n    for i in range(" + str(len(arm.gamerig.layers)) + "):")
        code.append("        arm.gamerig.layers.add()\n")

        for i in range(len(arm.gamerig.layers)):
            name = arm.gamerig.layers[i].name
            row = arm.gamerig.layers[i].row
            set = arm.gamerig.layers[i].selset
            group = arm.gamerig.layers[i].group
            code.append('    arm.gamerig.layers[' + str(i) + '].name = "' + name + '"')
            code.append('    arm.gamerig.layers[' + str(i) + '].row = ' + str(row))
            code.append('    arm.gamerig.layers[' + str(i) + '].selset = ' + str(set))
            code.append('    arm.gamerig.layers[' + str(i) + '].group = ' + str(group))

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
        code.append("    pbone.lock_location = %s" % str(tuple(pbone.lock_location)))
        code.append("    pbone.lock_rotation = %s" % str(tuple(pbone.lock_rotation)))
        code.append("    pbone.lock_rotation_w = %s" % str(pbone.lock_rotation_w))
        code.append("    pbone.lock_scale = %s" % str(tuple(pbone.lock_scale)))
        code.append("    pbone.rotation_mode = %r" % pbone.rotation_mode)
        if metarig:
            code.append("    pbone.bone.layers = %s" % str(list(pbone.bone.layers)))
        # Rig type parameters
        if pbone.gamerig.name:
            for i in pbone.gamerig.keys():
                param = getattr(pbone.gamerig, i, '')
                if str(type(param)) == "<class 'bpy_prop_array'>":
                    param = list(param)
                if type(param) == str:
                    param = '"' + param + '"'
                code.append("    try:")
                code.append("        pbone.gamerig.%s = %s" % (i, str(param)))
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
    if metarig:
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
