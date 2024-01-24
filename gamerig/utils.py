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
import importlib
import random
import string
import re
from mathutils import Vector, Color
from rna_prop_ui import rna_idprop_ui_create

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
    if len(t) > 1:
        return t[0] + text + '.' + t[1]
    else:
        m = re.search(r'_[lrLR]$', name)
        return name[0:-2] + text + m.group(0) if m else name + text


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
        bone_name_2 = edit_bone_2.name

        edit_bone_2.parent = edit_bone_1.parent
        edit_bone_2.use_connect = edit_bone_1.use_connect

        # Copy edit bone attributes
        for bcoll in edit_bone_1.collections:
            bcoll.assign(edit_bone_2)

        edit_bone_2.head = Vector(edit_bone_1.head)
        edit_bone_2.tail = Vector(edit_bone_1.tail)
        edit_bone_2.roll = edit_bone_1.roll

        edit_bone_2.use_inherit_rotation = edit_bone_1.use_inherit_rotation
        edit_bone_2.use_local_location = edit_bone_1.use_local_location
        edit_bone_2.inherit_scale = edit_bone_1.inherit_scale

        edit_bone_2.use_deform = edit_bone_1.use_deform

        if hasattr(edit_bone_1, 'bbone_curveinx'):
            edit_bone_2.bbone_curveinx = edit_bone_1.bbone_curveinx
        if hasattr(edit_bone_1, 'bbone_curveiny'):
            edit_bone_2.bbone_curveiny = edit_bone_1.bbone_curveiny
        if hasattr(edit_bone_1, 'bbone_curveoutx'):
            edit_bone_2.bbone_curveoutx = edit_bone_1.bbone_curveoutx
        if hasattr(edit_bone_1, 'bbone_curveouty'):
            edit_bone_2.bbone_curveouty = edit_bone_1.bbone_curveouty
        if hasattr(edit_bone_1, 'bbone_custom_handle_end'):
            edit_bone_2.bbone_custom_handle_end = edit_bone_1.bbone_custom_handle_end
        if hasattr(edit_bone_1, 'bbone_custom_handle_start'):
            edit_bone_2.bbone_custom_handle_start = edit_bone_1.bbone_custom_handle_start
        if hasattr(edit_bone_1, 'bbone_easein'):
            edit_bone_2.bbone_easein = edit_bone_1.bbone_easein
        if hasattr(edit_bone_1, 'bbone_easeout'):
            edit_bone_2.bbone_easeout = edit_bone_1.bbone_easeout
        if hasattr(edit_bone_1, 'bbone_handle_type_end'):
            edit_bone_2.bbone_handle_type_end = edit_bone_1.bbone_handle_type_end
        if hasattr(edit_bone_1, 'bbone_handle_type_start'):
            edit_bone_2.bbone_handle_type_start = edit_bone_1.bbone_handle_type_start
        if hasattr(edit_bone_1, 'bbone_rollin'):
            edit_bone_2.bbone_rollin = edit_bone_1.bbone_rollin
        if hasattr(edit_bone_1, 'bbone_rollout'):
            edit_bone_2.bbone_rollout = edit_bone_1.bbone_rollout
        if hasattr(edit_bone_1, 'bbone_scaleinx'):
            edit_bone_2.bbone_scaleinx = edit_bone_1.bbone_scaleinx
        if hasattr(edit_bone_1, 'bbone_scaleiny'):
            edit_bone_2.bbone_scaleiny = edit_bone_1.bbone_scaleiny
        if hasattr(edit_bone_1, 'bbone_scaleoutx'):
            edit_bone_2.bbone_scaleoutx = edit_bone_1.bbone_scaleoutx
        if hasattr(edit_bone_1, 'bbone_scaleouty'):
            edit_bone_2.bbone_scaleouty = edit_bone_1.bbone_scaleouty
        if hasattr(edit_bone_1, 'bbone_segments'):
            edit_bone_2.bbone_segments = edit_bone_1.bbone_segments
        if hasattr(edit_bone_1, 'bbone_x'):
            edit_bone_2.bbone_x = edit_bone_1.bbone_x
        if hasattr(edit_bone_1, 'bbone_z'):
            edit_bone_2.bbone_z = edit_bone_1.bbone_z

        if hasattr(edit_bone_1, 'head_radius'):
            edit_bone_2.head_radius = edit_bone_1.head_radius
        if hasattr(edit_bone_1, 'tail_radius'):
            edit_bone_2.tail_radius = edit_bone_1.tail_radius
        if hasattr(edit_bone_1, 'envelope_distance'):
            edit_bone_2.envelope_distance = edit_bone_1.envelope_distance
        if hasattr(edit_bone_1, 'envelope_weight'):
            edit_bone_2.envelope_weight = edit_bone_1.envelope_weight

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


def move_bone_collection_to(obj, bone_name, collection_name):
    if collection_name in obj.data.collections.keys():
        bone = obj.data.bones[bone_name]
        for col in bone.collections:
            col.unassign(bone)
        obj.data.collections[collection_name].assign(bone)


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


def bone_prop_link_driver(obj, bone_name, org_bone_name):
    # Copy custom properties
    bone = obj.pose.bones[bone_name]
    org_bone = obj.pose.bones[org_bone_name]
    rna_properties = {prop.identifier for prop in org_bone.bl_rna.properties if prop.is_runtime}
    for key1 in org_bone.keys():
        if key1 == '_RNA_UI' or key1 in rna_properties:
            continue
        if isinstance(org_bone[key1], float):
            prop1 = org_bone.id_properties_ui(key1)
            if prop1 is not None:
                key2 = f'{key1}({org_bone_name})'
                rna_idprop_ui_create(bone, key2, default=0.0, overridable=True)
                prop2 = bone.id_properties_ui(key2)
                if hasattr(prop1, 'keys'):
                    for k in prop1.keys():
                        prop2[k] = prop1[k]

                bone[key2] = org_bone[key1]

                drv = org_bone.driver_add(f'["{key1}"]').driver
                drv.type = 'AVERAGE'

                var = drv.variables.new()
                var.name = key2
                var.type = 'SINGLE_PROP'
                var.targets[0].id = obj
                var.targets[0].data_path = f'{bone.path_from_id()}["{key2}"]'


def bone_props_ui_string(obj, bone_name, org_bone_name):
    org_bone = obj.pose.bones[org_bone_name]
    rna_properties = {prop.identifier for prop in org_bone.bl_rna.properties if prop.is_runtime}
    ret = ""
    for key in org_bone.keys():
        if key == '_RNA_UI' or key in rna_properties:
            continue
        if isinstance(org_bone[key], float):
            ret += f"    layout.prop( pose_bones['{bone_name}'], '[\"{key}({org_bone_name})\"]', text='{key} ({org_bone_name})', slider = True )\n"

    if len(ret) > 0:
        return ret
    
    return None


def org_bone_props_ui_string(obj, bone_name, org_bone_name):
    org_bone = obj.pose.bones[org_bone_name]
    rna_properties = {prop.identifier for prop in org_bone.bl_rna.properties if prop.is_runtime}
    ret = ""
    for key in org_bone.keys():
        if key == '_RNA_UI' or key in rna_properties:
            continue
        if isinstance(org_bone[key], float):
            ret += f"    layout.prop( pose_bones['{org_bone_name}'], '[\"{key}\"]', text='{key} ({org_bone_name})', slider = True )\n"

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

    for _ in range(depth):
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

    # Bone Collection
    if metarig and len(arm.collections) > 0:
        code.append('\n    if len(arm.collections) > 0:')
        code.append('        for i in arm.collections:')
        code.append('            arm.collections.remove(i)')
        for col in arm.collections:
            code.append(f'    arm.collections.new("{col.name}")')
            code.append(f'    arm.collections[-1].gamerig.row = {col.gamerig.row}')
            code.append(f'    arm.collections[-1].gamerig.group = {col.gamerig.group}')

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
            for col in pbone.bone.collections:
                code.append(f"    arm.collections['{col.name}'].assign(pbone)")
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
