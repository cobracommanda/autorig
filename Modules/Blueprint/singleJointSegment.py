import os
import maya.cmds as cmds
import System.blueprint as blueprint_mod
import importlib
import System.utils as utils
importlib.reload(blueprint_mod)

CLASS_NAME = "SingleJointSegment"
TITLE = "Single Joint Segment"
DESCRIPTION = "Creates 2 joints, with controls for its joint orientation and rotate order. Ideal use: clavicle bone"
ICON = f"{os.environ['RIGGING_TOOL_ROOT']}/Icons/_singleJointSeg.xpm"


class SingleJointSegment(blueprint_mod.Blueprint):
    def __init__(self, user_specified_name, hook_obj) -> None:
        joint_info = [["root_joint", [0.0, 0.0, 0.0]], ["end_joint", [4.0, 0.0, 0.0]]]
        blueprint_mod.Blueprint.__init__(self, CLASS_NAME, user_specified_name, joint_info, hook_obj)

    def install_custom(self, joints):
        self.create_orientation_control(joints[0], joints[1])

    
    
    def lock_phase_1(self):
        """
        Gather and return all required information from this module's control objects
        joint_positions = a list of joint positions, from root down the hierarchy
        joint_orientations = a list of orientations, or a list of axis information (orient_joint and secondary_axis_orient for joint command)
                                # These are passed in the following tuple: (orientations, None) or (None, axis_info)
        joint_rotation_orders = a list of joint rotation orders (integer values gathered with getAttr)
        joint_preferred_angles = a list of joint preferred angles, optional (can pass None)
        hook_object = self.find_hook_object_for_lock()
        root_transform = a bool, either True or False. True = R,T, and S on root joint. False = R only
        module_info = (joint_positions, joint_orientations, joint_rotation_orders, joint_preferred_angles, hook_object)
        return module_info
        """
        joint_positions = []
        joint_orientations_values = []
        joint_rotation_orders = []
        joints = self.get_joints()
        
        
        for joint in joints:
            joint_positions.append(cmds.xform(joint, q=1, ws=1, t=1))
        
        clean_parent = f"{self.module_namespace}:joints_grp"
        orientation_info = self.orientation_controlled_joint_get_orientation(joints[0], clean_parent)
        cmds.delete(orientation_info[1])
        joint_orientations_values.append(orientation_info[0])
        joint_orientations = (joint_orientations_values, None)
        
        joint_rotation_orders.append(cmds.getAttr(f"{joints[0]}.rotateOrder"))
        joint_preferred_angles = None
        hook_object = self.find_hook_object_for_lock()
        root_transform = False
        
        module_info = (joint_positions, joint_orientations, joint_rotation_orders, joint_preferred_angles, hook_object, root_transform)
        return module_info
        
    def UI_custom(self):
        joints = self.get_joints()
        self.create_rotation_order_UI_control(joints[0])

    def create_rotation_order_UI_control(self, joint):
        joint_name = utils.strip_all_namespaces(joint)[1]
        self.blueprint_UI_instance.add_rotation_order_widget(f"Joint: {joint_name}", ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"], joint)
        
    def mirror_custom(self, original_module):
        joint_name = self.joint_info[0][0]
        original_joint = f"{original_module}:{joint_name}"
        new_joint = f"{self.module_namespace}:{joint_name}"
        
        original_orientation_control = self.get_orientation_control(original_joint)
        new_orientation_control = self.get_orientation_control(new_joint)
        
        cmds.setAttr(f"{new_orientation_control}.rotateX", cmds.getAttr(f"{original_orientation_control}.rotateX"))