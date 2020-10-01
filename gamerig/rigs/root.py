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

from ..utils import copy_bone, ctrlname, create_widget, bone_prop_link_driver, bone_props_ui_string


class Rig:
    """ root rig.
    """
    def __init__(self, obj, bone, metabone):
        """ Gather and validate data about the rig.
        """
        self.obj      = obj
        self.org_bone = bone
        self.params   = metabone.gamerig

    def generate(self, context):
        """ Generate the rig.
            Do NOT modify any of the original bones, except for adding constraints.
            The main armature should be selected and active before this is called.

        """
        # Make a control bone (copy of original).
        self.bone = copy_bone(self.obj, self.org_bone, ctrlname(self.org_bone))

        props_ui_str = bone_props_ui_string(self.obj, self.bone, self.org_bone)

        if props_ui_str:
            return f"""
if is_selected( '{self.bone}' ):
""" + props_ui_str


    def postprocess(self, context):
        pb = self.obj.pose.bones

        # Copy original bone lock state and rotation mode
        pb[self.bone].rotation_mode = pb[self.org_bone].rotation_mode
        pb[self.bone].lock_location = pb[self.org_bone].lock_location
        pb[self.bone].lock_rotation = tuple(pb[self.org_bone].lock_rotation)
        pb[self.bone].lock_rotation_w = pb[self.org_bone].lock_rotation_w
        pb[self.bone].lock_rotations_4d = pb[self.org_bone].lock_rotations_4d
        pb[self.bone].lock_location = tuple(pb[self.org_bone].lock_location)
        pb[self.bone].lock_scale = tuple(pb[self.org_bone].lock_scale)

        # Constrain the original bone.
        con = pb[self.org_bone].constraints.new('COPY_TRANSFORMS')
        con.name = "copy_transforms"
        con.target = self.obj
        con.subtarget = self.bone

        # add driver linked to original custom properties
        bone_prop_link_driver(self.obj, self.bone, self.org_bone)

        # Create control widget
        self.create_root_widget()

    def create_root_widget(self, bone_transform_name=None):
        """ Creates a widget for the root bone.
        """
        obj = create_widget(self.obj, self.bone, bone_transform_name)
        if obj != None:
            verts = [(0.70711, 0.70711, 0.0), (0.70711, -0.70711, 0.0), (-0.70711, 0.70711, 0.0), (-0.70711, -0.70711, 0.0), (0.83147, 0.55557, 0.0), (0.83147, -0.55557, 0.0), (-0.83147, 0.55557, 0.0), (-0.83147, -0.55557, 0.0), (0.92388, 0.38268, 0.0), (0.92388, -0.38268, 0.0), (-0.92388, 0.38268, 0.0), (-0.92388, -0.38268, 0.0), (0.98079, 0.19509, 0.0), (0.98079, -0.19509, 0.0), (-0.98079, 0.19509, 0.0), (-0.98079, -0.19509, 0.0), (0.19509, 0.98078, 0.0), (0.19509, -0.98078, 0.0), (-0.19509, 0.98078, 0.0), (-0.19509, -0.98078, 0.0), (0.38269, 0.92388, 0.0), (0.38269, -0.92388, 0.0), (-0.38269, 0.92388, 0.0), (-0.38269, -0.92388, 0.0), (0.55557, 0.83147, 0.0), (0.55557, -0.83147, 0.0), (-0.55557, 0.83147, 0.0), (-0.55557, -0.83147, 0.0), (0.19509, 1.2808, 0.0), (0.19509, -1.2808, 0.0), (-0.19509, 1.2808, 0.0), (-0.19509, -1.2808, 0.0), (1.2808, 0.19509, 0.0), (1.2808, -0.19509, 0.0), (-1.2808, 0.19509, 0.0), (-1.2808, -0.19509, 0.0), (0.39509, 1.2808, 0.0), (0.39509, -1.2808, 0.0), (-0.39509, 1.2808, 0.0), (-0.39509, -1.2808, 0.0), (1.2808, 0.39509, 0.0), (1.2808, -0.39509, 0.0), (-1.2808, 0.39509, 0.0), (-1.2808, -0.39509, 0.0), (0.0, 1.5808, 0.0), (0.0, -1.5808, 0.0), (1.5808, 0.0, 0.0), (-1.5808, 0.0, 0.0), ]
            if self.params.widget_plane == 'xz':
                for i in range(len(verts)):
                    verts[i] = (verts[i][0], verts[i][2], verts[i][1])
            elif self.params.widget_plane == 'yz':
                for i in range(len(verts)):
                    verts[i] = (verts[i][2], verts[i][0], verts[i][1])
            edges = [(0, 4), (1, 5), (2, 6), (3, 7), (4, 8), (5, 9), (6, 10), (7, 11), (8, 12), (9, 13), (10, 14), (11, 15), (16, 20), (17, 21), (18, 22), (19, 23), (20, 24), (21, 25), (22, 26), (23, 27), (0, 24), (1, 25), (2, 26), (3, 27), (16, 28), (17, 29), (18, 30), (19, 31), (12, 32), (13, 33), (14, 34), (15, 35), (28, 36), (29, 37), (30, 38), (31, 39), (32, 40), (33, 41), (34, 42), (35, 43), (36, 44), (37, 45), (38, 44), (39, 45), (40, 46), (41, 46), (42, 47), (43, 47), ]
            mesh = obj.data
            mesh.from_pydata(verts, edges, [])
            mesh.update()


def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigParameters PropertyGroup
    """
    params.widget_plane = bpy.props.EnumProperty(
        items   = [
            ('xy', 'XY', 'XY Plane'),
            ('xz', 'XZ', 'XZ Plane'),
            ('yz', 'YZ', 'YZ Plane')
        ],
        name    = "Widget Plane",
        default = 'xy'
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "widget_plane")


def create_sample(obj):
    """ Create a sample metarig for this rig type.
    """
    # generated by gamerig.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.0000, 1.0000, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.use_deform = False
    bones['Bone'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bone']]
    pbone.gamerig.name = 'root'
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
