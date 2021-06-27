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
import re
import time
import traceback
import sys
from rna_prop_ui import rna_idprop_ui_prop_get
from .utils import (
    rig_module_name, get_rig_type, create_widget, assign_all_widgets,
    is_org, is_mch, is_jig, random_id, basename,
    copy_attributes, gamma_correct, get_rig_name, copy_bone,
    begin_progress, update_progress, end_progress,
    MetarigError
)
from . import rig_lists
from mathutils import Vector


RIG_MODULE = "rigs"
ORG_LAYER = [n == 31 for n in range(0, 32)]  # Armature layer that original bones should be moved to.
MCH_LAYER = [n == 30 for n in range(0, 32)]  # Armature layer that mechanism bones should be moved to.


class Timer:
    def __init__(self):
        self.timez = time.time()

    def tick(self, string):
        t = time.time()
        print(string + "%.3f" % (t - self.timez))
        self.timez = t


def generate_rig(context, metarig):
    """ Generates a rig from a metarig.
    """
    t = Timer()

    # clear created widget list
    if hasattr(create_widget, 'created_widgets'):
        del create_widget.created_widgets
    # clear copied bone list
    if hasattr(copy_bone, 'copied'):
        del copy_bone.copied

    # Find overwrite target rig if exists
    rig_name = get_rig_name(metarig)

    # store rig name to property if rig name already not stored.
    if not metarig.data.gamerig.rig_name:
        metarig.data.gamerig.rig_name = rig_name

    print("Fetch rig (%s)." % rig_name)
    obj = next((i for i in context.collection.objects if i != metarig and i.type == 'ARMATURE' and i.name == rig_name), None)
    if obj and not obj in context.visible_objects:
        return "GAMERIG ERROR: Overwritee rig '%s' is hidden. Cannot Operate." % obj.name

    # Random string with time appended so that
    # different rigs don't collide id's
    rig_id = (obj.data.get("gamerig_id") if obj else None) or random_id()

    # Initial configuration
    rest_backup = metarig.data.pose_position
    metarig.data.pose_position = 'REST'

    bpy.ops.object.mode_set(mode='OBJECT')

    view_layer = context.view_layer
    collection = context.collection
    layer_collection = context.layer_collection
    #------------------------------------------
    # Create/find the rig object and set it up

    # Check if the generated rig already exists, so we can
    # regenerate in the same object.  If not, create a new
    # object to generate the rig in.
    
    previous_action = None
    previous_nla_tracks = None
    previous_nla_strips = {}
    toggledArmatureModifiers = []
    if obj:
        print("Overwrite existing rig.")
        try:
            # toggle armature object to metarig if it using generated rig.
            # (referensing rig overwriting makes script runs very slowly)
            for i in collection.objects:
                for j in i.modifiers:
                    if j.type == 'ARMATURE' and j.object == obj:
                        toggledArmatureModifiers.append(j)
                        j.object = metarig
            # Get rid of anim data in case the rig already existed
            print("Clear rig animation data.")
            if obj.animation_data:
                previous_action = obj.animation_data.action
                previous_nla_tracks = tuple(obj.animation_data.nla_tracks)
                for i in previous_nla_tracks:
                    previous_nla_strips[i] = tuple(i.strips)
            obj.animation_data_clear()
            obj.data.animation_data_clear()
        except KeyError:
            print("Overwrite failed.")
            obj = None
    
    if obj is None:
        print("Create new rig.")
        name = metarig.data.gamerig.rig_name or "rig"
        obj = bpy.data.objects.new(name, bpy.data.armatures.new(name))  # in case name 'rig' exists it will be rig.001
        obj.display_type = 'WIRE'
        collection.objects.link(obj)
        # Put the rig_name in the armature custom properties
        rna_idprop_ui_prop_get(obj.data, "gamerig_id", create=True)
        obj.data["gamerig_id"] = rig_id
        obj.location            = metarig.location
        obj.rotation_mode       = metarig.rotation_mode
        obj.rotation_euler      = metarig.rotation_euler
        obj.rotation_quaternion = metarig.rotation_quaternion
        obj.rotation_axis_angle = metarig.rotation_axis_angle
        obj.scale               = metarig.scale

    # apply rotation for metarig / rig
    bpy.ops.object.select_all(action='DESELECT')
    metarig_rotation_euler_backup      = metarig.rotation_euler.copy()
    metarig_rotation_quaternion_backup = metarig.rotation_quaternion.copy()
    metarig_rotation_axis_angle_backup = Vector(metarig.rotation_axis_angle)
    rig_rotation_euler_backup      = obj.rotation_euler.copy()
    rig_rotation_quaternion_backup = obj.rotation_quaternion.copy()
    rig_rotation_axis_angle_backup = Vector(obj.rotation_axis_angle)
    metarig_needs_apply_rot = abs(metarig_rotation_axis_angle_backup.angle) > 0 if metarig.rotation_mode == 'AXIS_ANGLE' else \
        abs(metarig_rotation_quaternion_backup.angle) > 0 if metarig.rotation_mode == 'QUATERNION' else \
        abs(metarig_rotation_euler_backup.x) > 0 or abs(metarig_rotation_euler_backup.y) > 0 or abs(metarig_rotation_euler_backup.z) > 0
    obj_needs_apply_rot = abs(rig_rotation_axis_angle_backup.angle) > 0 if obj.rotation_mode == 'AXIS_ANGLE' else \
        abs(rig_rotation_quaternion_backup.angle) > 0 if obj.rotation_mode == 'QUATERNION' else \
        abs(rig_rotation_euler_backup.x) > 0 or abs(rig_rotation_euler_backup.y) > 0 or abs(rig_rotation_euler_backup.z) > 0
    metarig.select_set(metarig_needs_apply_rot)
    obj.select_set(obj_needs_apply_rot)
    if metarig_needs_apply_rot or obj_needs_apply_rot:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    obj.data.pose_position = 'POSE'

    # Select generated rig object
    metarig.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj

    # Get parented objects to restore later
    childs = {}  # {object: bone}
    for child in obj.children:
        childs[child] = child.parent_bone

    # Remove all bones from the generated rig armature.
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in obj.data.edit_bones:
        obj.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Create temporary duplicates for merging
    temp_rig_1 = metarig.copy()
    temp_rig_1.data = metarig.data.copy()
    collection.objects.link(temp_rig_1)

    temp_rig_2 = metarig.copy()
    temp_rig_2.data = obj.data
    collection.objects.link(temp_rig_2)

    # Select the temp rigs for merging
    for objt in collection.objects:
        objt.select_set(False)  # deselect all objects
    temp_rig_1.select_set(True)
    temp_rig_2.select_set(True)
    view_layer.objects.active = temp_rig_2

    # Merge the temporary rigs
    bpy.ops.object.join()

    # Delete the second temp rig
    bpy.ops.object.delete()

    # Select the generated rig
    for objt in view_layer.objects:
        objt.select_set(False)  # deselect all objects
    obj.select_set(True)
    view_layer.objects.active = obj

    # Copy metarig's Custom properties to rig
    for prop in metarig.data.keys():
        try:
            if prop != "_RNA_UI" and prop != "gamerig" and prop != "gamerig_id":
                obj.data[prop] = metarig.data[prop]
        except KeyError:
            pass

    # Copy over bone properties
    for bone in metarig.data.bones:
        bone_gen = obj.data.bones[bone.name]

        # B-bone stuff
        bone_gen.bbone_segments = bone.bbone_segments
        bone_gen.bbone_easein = bone.bbone_easein
        bone_gen.bbone_easeout = bone.bbone_easeout

    # Copy over the pose_bone properties
    for bone in metarig.pose.bones:
        bone_gen = obj.pose.bones[bone.name]

        # Rotation mode and transform locks
        bone_gen.rotation_mode = bone.rotation_mode
        bone_gen.lock_rotation = tuple(bone.lock_rotation)
        bone_gen.lock_rotation_w = bone.lock_rotation_w
        bone_gen.lock_rotations_4d = bone.lock_rotations_4d
        bone_gen.lock_location = tuple(bone.lock_location)
        bone_gen.lock_scale = tuple(bone.lock_scale)

        # Custom properties
        for prop in bone.keys():
            try:
                bone_gen[prop] = bone[prop]
            except KeyError:
                pass

    # Clear drivers
    if obj.animation_data:
        for d in obj.animation_data.drivers:
            try:
                obj.driver_remove(d.data_path)
            except TypeError:
                pass
    
    t.tick("Duplicate rig: ")
    #----------------------------------
    # Make a list of the original bones so we can keep track of them.
    original_bones = [bone.name for bone in obj.data.bones]

    # Create a sorted list of the original bones, sorted in the order we're
    # going to traverse them for rigging.
    # (root-most -> leaf-most, alphabetical)
    bones_sorted = []
    for name in original_bones:
        bones_sorted.append(name)
    bones_sorted.sort()  # first sort by names
    bones_sorted.sort(key=lambda bone: len(obj.pose.bones[bone].parent_recursive))  # then parents before children
    t.tick("Make list of org bones: ")

    #----------------------------------
    error = None
    def append_error(bone, rig, e):
        nonlocal error
        errorstr  = "failed at rig '%s' (%s)." % (bone, rig.__class__.__module__) if rig else "failed at rig '%s'." % bone
        errorstr += "\n   " + e.message
        print("GameRig: %s" % errorstr)
        if error:
            error += '\n' + errorstr
        else:
            error = errorstr
    
    try:
        # Collect/initialize all the rigs.
        rigs = {}
        rigtypes = set()
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in bones_sorted:
            try:
                rig = get_bone_rig(metarig, obj, bone, rigtypes)
                if rig:
                    rigs[bone] = rig
            except MetarigError as e:
                append_error(bone, None, e)
        t.tick("Initialize rigs: ")

        begin_progress(len(rigs.keys()) * 2)

        # Generate all the rigs.
        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)
        tt = Timer()
        ui_scripts = []

        # Go into editmode in the rig armature
        bpy.ops.object.mode_set(mode='EDIT')
        for bone, rig in dict(rigs.items()).items():
            try:
                script = rig.generate(context)
                if script and len(script) > 0:
                    ui_scripts.append(script)
            except MetarigError as e:
                append_error(bone, rig, e)
                del rigs[bone]
            tt.tick("Generate rig : %s (%s): " % (bone, rig.__class__.__module__))
            update_progress()

        # Go into objectmode in the rig armature
        bpy.ops.object.mode_set(mode='OBJECT')

        # Copy Constraints
        for bone in metarig.pose.bones:
            bone_gen = obj.pose.bones[bone.name]
            
            for con1 in bone.constraints:
                con2 = bone_gen.constraints.new(type=con1.type)
                copy_attributes(con1, con2)

                # Set metarig target to rig target
                if "target" in dir(con2):
                    if con2.target == metarig:
                        con2.target = obj

        # Copy drivers
        if metarig.animation_data:
            for d1 in metarig.animation_data.drivers:
                d2 = obj.driver_add(d1.data_path)
                copy_attributes(d1, d2)
                copy_attributes(d1.driver, d2.driver)

                # Remove default modifiers, variables, etc.
                for m in d2.modifiers:
                    d2.modifiers.remove(m)
                for v in d2.driver.variables:
                    d2.driver.variables.remove(v)

                # Copy modifiers
                for m1 in d1.modifiers:
                    m2 = d2.modifiers.new(type=m1.type)
                    copy_attributes(m1, m2)

                # Copy variables
                for v1 in d1.driver.variables:
                    v2 = d2.driver.variables.new()
                    copy_attributes(v1, v2)
                    for i in range(len(v1.targets)):
                        copy_attributes(v1.targets[i], v2.targets[i])
                        # Switch metarig targets to rig targets
                        if v2.targets[i].id == metarig:
                            v2.targets[i].id = obj

                        # Mark targets that may need to be altered after rig generation
                        target = v2.targets[i]
                        # If a custom property
                        if v2.type == 'SINGLE_PROP' and re.match('^pose.bones\["[^"\]]*"\]\["[^"\]]*"\]$', target.data_path):
                            target.data_path = "GAMERIG-" + target.data_path

                # Copy key frames
                try:
                    for i in range(len(d1.keyframe_points)):
                        d2.keyframe_points.add()
                        k1 = d1.keyframe_points[i]
                        k2 = d2.keyframe_points[i]
                        copy_attributes(k1, k2)
                except TypeError:
                    pass
        
        for bone, rig in rigs.items():
            try:
                rig.postprocess(context)
            except MetarigError as e:
                append_error(bone, rig, e)
            tt.tick("PostProcess rig : %s (%s): " % (bone, rig.__class__.__module__))
            update_progress()
        t.tick("Generate rigs: ")
    except Exception as e:
        # Cleanup if something goes wrong
        print("GameRig: failed to generate rig.")
        metarig.data.pose_position = rest_backup
        obj.data.pose_position = 'POSE'
        bpy.ops.object.mode_set(mode='OBJECT')

        # Continue the exception
        raise e
    finally:
        end_progress()

    # Alter marked driver targets
    if obj.animation_data:
        for d in obj.animation_data.drivers:
            for v in d.driver.variables:
                for target in v.targets:
                    if target.data_path.startswith("GAMERIG-"):
                        temp, bone, prop = tuple([x.strip('"]') for x in target.data_path.split('["')])
                        if bone in obj.data.bones and prop in obj.pose.bones[bone].keys():
                            target.data_path = target.data_path[7:]
                        else:
                            target.data_path = 'pose.bones["%s"]["%s"]' % (basename(bone), prop) #?

    # Get a list of all the bones in the armature
    bones = [bone.name for bone in obj.data.bones]
    metabones = [bone.name for bone in metarig.data.bones]

    # All the others make non-deforming.
    for bone in bones:
        if not (is_org(bone) or bone in metabones):
            b = obj.data.bones[bone]
            b.use_deform = False

    # Move all the original bones to their layer.
    for bone in original_bones:
        obj.data.bones[bone].layers = ORG_LAYER

    # Move all the bones with names starting with "MCH-" to their layer.
    for bone in bones:
        if is_mch(obj.data.bones[bone].name):
            obj.data.bones[bone].layers = MCH_LAYER

    # Assign shapes to bones
    assign_all_widgets(obj)
    # Reveal all the layers with control bones on them
    vis_layers = [False for n in range(0, 32)]
    for bone in bones:
        for i in range(0, 32):
            vis_layers[i] = vis_layers[i] or obj.data.bones[bone].layers[i]
    for i in range(0, 32):
        vis_layers[i] = vis_layers[i] and not (ORG_LAYER[i] or MCH_LAYER[i])
    obj.data.layers = vis_layers

    # Ensure the collection of layer names exists
    for i in range(1 + len(metarig.data.gamerig.layers), 30):
        metarig.data.gamerig.layers.add()

    # Create list of layer name/row pairs
    layer_layout = []
    for l in metarig.data.gamerig.layers:
        #print(l.name)
        layer_layout.append((l.name, l.row))

    # Generate the UI script
    rig_ui_name = 'gamerig_ui_%s.py' % rig_id

    if rig_ui_name in bpy.data.texts.keys():
        script = bpy.data.texts[rig_ui_name]
        try:
            script.as_module().unregister()
        except:
            pass
        script.clear()
    else:
        script = bpy.data.texts.new(rig_ui_name)

    operator_scripts = ''
    for rigt in rigtypes:
        try:
            rigt.operator_script
        except AttributeError:
            pass
        else:
            operator_scripts += rigt.operator_script(rig_id)

    uitemplate = rig_lists.riguitemplate_dic[metarig.data.gamerig.rig_ui_template]

    script.write(
        uitemplate[0].format(
            rig_id=rig_id,
            operators=operator_scripts,
            properties=properties_ui(ui_scripts),
            layers=layers_ui(vis_layers, layer_layout)
        )
    )
    script.use_module = True

    # Register UI script
    try:
        script.as_module().register()
    except AttributeError:
        pass
    else:
        operator_scripts += rigt.operator_script(rig_id)

    # Create Selection Sets
    create_selection_sets(obj, metarig)

    # Create Bone Groups
    create_bone_groups(obj, metarig)

    # Remove all jig bones.
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in [bone.name for bone in obj.data.edit_bones]:
        if is_jig(bone):
            obj.data.edit_bones.remove(obj.data.edit_bones[bone])

    #----------------------------------
    # Deconfigure
    bpy.ops.object.mode_set(mode='OBJECT')

    # Restore original rotation

    if metarig_needs_apply_rot or obj_needs_apply_rot:

        metarig_rotation_euler_inverted = metarig_rotation_euler_backup.copy()
        metarig_rotation_euler_inverted.x *= -1
        metarig_rotation_euler_inverted.y *= -1
        metarig_rotation_euler_inverted.z *= -1

        metarig_rotation_axis_angle_inverted = metarig_rotation_axis_angle_backup.copy()
        metarig_rotation_axis_angle_inverted.w *= -1

        metarig.rotation_euler      = metarig_rotation_euler_inverted
        metarig.rotation_quaternion = metarig_rotation_quaternion_backup.inverted()
        metarig.rotation_axis_angle = metarig_rotation_axis_angle_inverted

        rig_rotation_euler_inverted = rig_rotation_euler_backup.copy()
        rig_rotation_euler_inverted.x *= -1
        rig_rotation_euler_inverted.y *= -1
        rig_rotation_euler_inverted.z *= -1

        rig_rotation_axis_angle_inverted = rig_rotation_axis_angle_backup.copy()
        rig_rotation_axis_angle_inverted.w *= -1

        obj.rotation_euler      = rig_rotation_euler_inverted
        obj.rotation_quaternion = rig_rotation_quaternion_backup.inverted()
        obj.rotation_axis_angle = rig_rotation_axis_angle_inverted

        bpy.ops.object.select_all(action='DESELECT')
        metarig.select_set(metarig_needs_apply_rot)
        obj.select_set(obj_needs_apply_rot)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    for ob in bpy.data.objects:
        if ob.parent == obj:
            for i in range(len(ob.rotation_euler)):
                if abs(ob.rotation_euler[i]) <= sys.float_info.epsilon:
                    ob.rotation_euler[i] = 0
            for i in range(len(ob.rotation_quaternion)):
                if abs(ob.rotation_quaternion[i]) <= sys.float_info.epsilon:
                    ob.rotation_quaternion[i] = 0
            for i in range(len(ob.rotation_axis_angle)):
                if abs(ob.rotation_axis_angle[i]) <= sys.float_info.epsilon:
                    ob.rotation_axis_angle[i] = 0

    metarig.rotation_euler      = metarig_rotation_euler_backup
    metarig.rotation_quaternion = metarig_rotation_quaternion_backup
    metarig.rotation_axis_angle = metarig_rotation_axis_angle_backup

    obj.rotation_euler      = rig_rotation_euler_backup
    obj.rotation_quaternion = rig_rotation_quaternion_backup
    obj.rotation_axis_angle = rig_rotation_axis_angle_backup
    
    metarig.select_set(False)
    obj.select_set(True)

    metarig.data.pose_position = rest_backup
    
    obj.data.pose_position = 'POSE'

    # Restore toggled armature modifiers
    for i in toggledArmatureModifiers:
        i.object = obj
    # Restore parent to bones
    for child, sub_parent in childs.items():
        if sub_parent in obj.pose.bones:
            mat = child.matrix_world.copy()
            child.parent_bone = sub_parent
            child.matrix_world = mat
    # Restore active collection
    view_layer.active_layer_collection = layer_collection

    # Restore action and NLA tracks
    if previous_action:
        obj.animation_data.action = previous_action
    if previous_nla_tracks:
        try:
            for s in previous_nla_tracks:
                d = obj.animation_data.nla_tracks.new()
                copy_attributes(s, d)
                for ss in previous_nla_strips[s]:
                    dd = d.strips.new(ss.name, ss.frame_start, ss.action)
                    copy_attributes(ss, dd)
        except Exception as e:
            print("GameRig: Warning. failed to restore NLA tracks.")

    t.tick("The rest: ")
    return error


def create_selection_sets(obj, metarig):

    # Check if selection sets addon is installed
    if 'bone_selection_groups' not in bpy.context.preferences.addons and 'bone_selection_sets' not in bpy.context.preferences.addons:
        return

    bpy.ops.object.mode_set(mode='POSE')

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    metarig.select_set(False)
    pbones = obj.pose.bones

    for i, name in enumerate(metarig.data.gamerig.layers.keys()):
        if name == '' or not metarig.data.gamerig.layers[i].selset:
            continue

        bpy.ops.pose.select_all(action='DESELECT')
        for b in pbones:
            if b.bone.layers[i]:
                b.bone.select = True

        #bpy.ops.pose.selection_set_add()
        obj.selection_sets.add()
        obj.selection_sets[-1].name = name
        if 'bone_selection_sets' in bpy.context.preferences.addons:
            act_sel_set = obj.selection_sets[-1]

            # iterate only the selected bones in current pose that are not hidden
            for bone in bpy.context.selected_pose_bones:
                if bone.name not in act_sel_set.bone_ids:
                    bone_id = act_sel_set.bone_ids.add()
                    bone_id.name = bone.name


def create_bone_groups(obj, metarig):

    bpy.ops.object.mode_set(mode='OBJECT')
    pb = obj.pose.bones
    layers = metarig.data.gamerig.layers
    groups = metarig.data.gamerig.colors

    # Create BGs
    for l in layers:
        if l.group == 0:
            continue
        g_id = l.group - 1
        name = groups[g_id].name
        if name not in obj.pose.bone_groups.keys():
            bg = obj.pose.bone_groups.new(name=name)
            bg.color_set = 'CUSTOM'
            bg.colors.normal = gamma_correct(groups[g_id].normal)
            bg.colors.select = gamma_correct(groups[g_id].select)
            bg.colors.active = gamma_correct(groups[g_id].active)

    for b in pb:
        try:
            layer_index = b.bone.layers[:].index(True)
        except ValueError:
            continue
        if layer_index > len(layers) - 1:   # bone is on reserved layers
            continue
        g_id = layers[layer_index].group - 1
        if g_id >= 0:
            name = groups[g_id].name
            b.bone_group = obj.pose.bone_groups[name]


def get_bone_rig(metarig, obj, bone_name, rigtypes, halt_on_missing=False):
    """ Fetch all the rigs specified on a bone.
    """
    rig_type = metarig.pose.bones[bone_name].gamerig.name
    rig_type = rig_type.replace(" ", "")

    if rig_type == "":
        pass
    else:
        # Get the rig
        try:
            rigt = next((rigt.__name__ == rig_module_name(rig_type) for rigt in rigtypes), None)
            if not rigt:
                rigt = get_rig_type(rig_type)
            rig = rigt.Rig(obj, bone_name, metarig.pose.bones[bone_name])
        except ImportError:
            message = "Rig Type Missing: python module for type '%s' not found (bone: %s)" % (rig_type, bone_name)
            if halt_on_missing:
                raise MetarigError(message)
            else:
                print(message)
                print('print_exc():')
                traceback.print_exc(file=sys.stdout)
        else:
            rigtypes.add(rigt)
            return rig


def get_xy_spread(bones):
    x_max = 0
    y_max = 0
    for b in bones:
        x_max = max((x_max, abs(b.head[0]), abs(b.tail[0])))
        y_max = max((y_max, abs(b.head[1]), abs(b.tail[1])))

    return max((x_max, y_max))


def param_matches_type(param_name, rig_type):
    """ Returns True if the parameter name is consistent with the rig type.
    """
    if param_name.rsplit(".", 1)[0] == rig_type:
        return True
    else:
        return False


def param_name(param_name, rig_type):
    """ Get the actual parameter name, sans-rig-type.
    """
    return param_name[len(rig_type) + 1:]


def properties_ui(scripts):
    """ Turn a concatened string of Property UI scripts.
    """
    code = ""
    for s in scripts:
        code += "\n        " + s.replace("\n", "\n        ") + "\n"
    return code


def layers_ui(layers, layout):
    """ Turn a list of booleans + a list of names into a layer UI.
    """

    rows = {}
    for i in range(30):
        if layers[i]:
            if layout[i][1] not in rows:
                rows[layout[i][1]] = []
            rows[layout[i][1]].append((layout[i][0], i))

    keys = list(rows.keys())
    keys.sort()

    code = ""

    for key in keys:
        code += "\n        row = col.row()\n"
        i = 0
        for l in rows[key]:
            if i > 3:
                code += "\n        row = col.row()\n"
                i = 0
            code += "        row.prop(context.active_object.data, 'layers', index=%s, toggle=True, text='%s')\n" % (str(l[1]), l[0])
            i += 1

    return code
