import os  # Import os for file operations
import maya.cmds as cmds  # Import Maya commands module
import System.utils as utils  # Import custom utility functions
from PySide2 import QtWidgets
import importlib




class Blueprint:
    def __init__(self, module_name, user_specified_name, joint_info, hook_obj_in) -> None:
        self.module_name = module_name
        self.user_specified_name = user_specified_name
        self.module_namespace = f"{self.module_name}__{self.user_specified_name}"  # Set namespace
        self.container_name = f"{self.module_namespace}:module_container"  # Set container name
        self.joint_info = joint_info
        self.hook_object = None
        if hook_obj_in != None:
            partition_info = hook_obj_in.rpartition("_translation_control")
            if partition_info[1] != "" and partition_info[2] == "":
                self.hook_object = hook_obj_in
        
        self.module_can_be_mirrored = True
        self.mirrored = False
        
        
    # Method to be overridden by derived class
    def install_custom(self, joints):
        print("install_custom() method is not implemented by derived class")  

    def UI_custom(self):
        pass  

    def lock_phase_1(self):
        """
        Gather and return all required information from this module's control objects.
        joint_positions = a list of joint positions, from root down the hierarchy.
        joint_orientations = a list of orientations, or a list of axis information (orient_joint and secondary_axis_orient for joint command).
        joint_rotation_orders = a list of joint rotation orders (integer values gathered with getAttr).
        joint_preferred_angles = a list of joint preferred angles, optional (can pass None).
        hook_object = self.find_hook_object_for_lock().
        root_transform = a bool, either True or False. True = R, T, and S on root joint. False = R only.
        module_info = (joint_positions, joint_orientations, joint_rotation_orders, joint_preferred_angles, hook_object).
        return module_info.
        """
        return None
    
    
    def mirror_custom(self, original_module):
        print("mirror_custom() method is not implemented by derived class")
    
    # Base Class Methods
    def install(self):
        cmds.namespace(setNamespace=":")  # Set namespace to root
        cmds.namespace(add=self.module_namespace)  # Add namespace
        self.joints_grp = cmds.group(empty=True, name=f"{self.module_namespace}:joints_grp")  # Create joints group
        self.hierarchy_representation_grp = cmds.group(em=1, n=f"{self.module_namespace}:hierarchy_representation_grp")  # Create hierarchy representation group

        self.orientation_controls_grp = cmds.group(em=1, n=f"{self.module_namespace}:orientationControls_grp")  # Create orientation controls group
        self.module_grp = cmds.group([self.joints_grp, self.hierarchy_representation_grp, self.hierarchy_representation_grp, self.orientation_controls_grp], name=f"{self.module_namespace}:module_grp")  # Create module group

        if not cmds.objExists(self.container_name):
            cmds.container(name=self.container_name)  # Create container
        utils.add_node_to_container(self.container_name, self.module_grp, ihb=1)  # Add node to container

        cmds.select(clear=True)

        index = 0
        joints = []

        for joint in self.joint_info:
            joint_name = joint[0]
            joint_pos = joint[1]

            parent_joint = ""
            if index > 0:
                parent_joint = f"{self.module_namespace}:{self.joint_info[index - 1][0]}"
                cmds.select(parent_joint, replace=True)

            joint_name_full = cmds.joint(n=f"{self.module_namespace}:{joint_name}", p=joint_pos)  # Create joint
            joints.append(joint_name_full)

            cmds.setAttr(f"{joint_name_full}.visibility", 0)  # Hide joint
            utils.add_node_to_container(self.container_name, joint_name_full)  # Add joint to container

            cmds.container(self.container_name, edit=True, publishAndBind=[f"{joint_name_full}.rotate", f"{joint_name}_R"])  # Publish rotate attribute
            cmds.container(self.container_name, edit=True, publishAndBind=[f"{joint_name_full}.rotateOrder", f"{joint_name}_rotateOrder"])  # Publish rotate order attribute

            if index > 0:
                cmds.joint(parent_joint, edit=True, orientJoint="xyz", sao="yup")  # Orient joint

            index += 1
        
        if self.mirrored:
            mirror_XY = False
            mirror_YZ = False
            mirror_XZ = False
            
            if self.mirror_plane == "XY":
                mirror_XY = True
            elif self.mirror_plane == "YZ":
                mirror_YZ = True
            elif self.mirror_plane == "XZ":
                mirror_XZ = True
                
            mirror_behavior = False
            if self.rotation_function == "behavior":
                mirror_behavior = True
            
            mirror_nodes = cmds.mirrorJoint(joints[0], mxy=mirror_XY, myz=mirror_YZ, mxz=mirror_XZ, mb=mirror_behavior)
            cmds.delete(joints)
            
            mirror_joints = []
            
            for node in mirror_nodes:
                if cmds.objectType(node, isa="joint"):
                    mirror_joints.append(node)
                else:
                    cmds.delete(node)
            
            index = 0
            
            for joint in mirror_joints:
                joint_name = self.joint_info[index][0]
                new_joint_name = cmds.rename(joint, f"{self.module_namespace}:{joint_name}")
                self.joint_info[index][1] = cmds.xform(new_joint_name, q=1, ws=1, t=1)
                
                index += 1
            # return
                

        cmds.parent(joints[0], self.joints_grp, absolute=True)  # Parent first joint to joints group

        self.initialize_module_transform(self.joint_info[0][1])  # Initialize module transform

        translations_controls = []
        for joint in joints:
            translations_controls.append(self.create_translation_controller_at_joints(joint))  # Create translation controllers

        root_joint_point_constraint = cmds.pointConstraint(translations_controls[0], joints[0], mo=0, n=f"{joints[0]}_pointConstraint")  # Create point constraint
        utils.add_node_to_container(self.container_name, root_joint_point_constraint)  # Add point constraint to container
        
        
        self.initialize_hook(translations_controls[0]) # Initialize hook

        for index in range(len(joints) - 1):
            self.setup_stretchy_joint_segment(joints[index], joints[index+1])  # Setup stretchy joint segment

        self.install_custom(joints)  # Call custom install method

        utils.force_scene_update()  # Force scene update
        cmds.lockNode(self.container_name, lock=True, lockUnpublished=True)  # Lock container

    def create_translation_controller_at_joints(self, joint):
        pos_control_file = f"{os.environ['RIGGING_TOOL_ROOT']}/ControlObjects/Blueprint/translation_control.ma"
        cmds.file(pos_control_file, i=True)  # Import translation control file

        container = cmds.rename("translation_control_container", f"{joint}_translation_control_container")  # Rename container

        utils.add_node_to_container(self.container_name, container)  # Add container to module container

        for node in cmds.container(container, q=True, nodeList=True):
            cmds.rename(node, f"{joint}_{node}", ignoreShape=True)  # Rename nodes

        control = f"{joint}_translation_control"

        cmds.parent(control, self.module_transform, a=1)  # Parent control to module transform

        joint_pos = cmds.xform(joint, q=True, worldSpace=True, translation=True)  # Get joint position
        cmds.xform(control, worldSpace=True, absolute=True, translation=joint_pos)  # Set control position

        nice_name = utils.strip_leading_namespace(joint)[1]

        attr_name = f"{nice_name}_T"

        cmds.container(container, edit=True, publishAndBind=[f"{control}.translate", attr_name])  # Publish translate attribute
        cmds.container(self.container_name, edit=True, publishAndBind=[f"{container}.{attr_name}", attr_name])  # Publish attribute to module container

        return control

    def get_translation_control(self, joint_name):
        return f"{joint_name}_translation_control"  # Get translation control name

    def setup_stretchy_joint_segment(self, parent_joint, child_joint):
        parent_translation_control = self.get_translation_control(parent_joint)  # Get parent translation control
        child_translation_control = self.get_translation_control(child_joint)  # Get child translation control

        pole_vector_locator = cmds.spaceLocator(n=f"{parent_translation_control}_poleVectorLocator")[0]  # Create pole vector locator
        pole_vector_locator_grp = cmds.group(n=f"{pole_vector_locator}_parentConstraintGrp")  # Create group for pole vector locator

        cmds.parent(pole_vector_locator_grp, self.module_grp, a=1)  # Parent group to module group
        parent_constraint = cmds.parentConstraint(parent_translation_control, pole_vector_locator_grp, mo=0)[0]  # Create parent constraint
        cmds.setAttr(f"{pole_vector_locator}.visibility", 0)  # Hide pole vector locator
        cmds.setAttr(f"{pole_vector_locator}.ty", -0.5)  # Set pole vector locator position

        ik_nodes = utils.basic_stretchy_IK(parent_joint, child_joint, container=self.container_name, lockMinimumLength=False,
                                           poleVectorObject=pole_vector_locator, scaleCorrectionAttribute=None)  # Setup basic stretchy IK

        ik_handle = ik_nodes['ik_handle']
        root_locator = ik_nodes['root_locator']
        end_locator = ik_nodes['end_locator']
        
        if self.mirrored:
            if self.mirror_plane == "XZ":
                cmds.setAttr(f"{ik_handle}.twist", 90)

        child_point_constraint = cmds.pointConstraint(child_translation_control, end_locator, mo=0, n=f"{end_locator}_pointConstraint")[0]  # Create point constraint

        utils.add_node_to_container(self.container_name, [pole_vector_locator_grp, parent_constraint, child_point_constraint], ihb=1)  # Add nodes to container

        for node in [ik_handle, root_locator, end_locator]:
            cmds.parent(node, self.joints_grp, a=1)  # Parent nodes to joints group
            cmds.setAttr(f"{node}.visibility", 0)  # Hide nodes

        self.create_hierarchy_representation(parent_joint, child_joint)  # Create hierarchy representation

    def create_hierarchy_representation(self, parent_joint, child_joint):
        nodes = self.create_stretchy_object("/ControlObjects/Blueprint/hierarchy_representation.ma", "hierarchy_representation_container",
                                            "hierarchy_representation", parent_joint, child_joint)  # Create stretchy object

        constrained_grp = nodes[2]
        cmds.parent(constrained_grp, self.hierarchy_representation_grp, r=1)  # Parent group to hierarchy representation group

    def create_stretchy_object(self, object_relative_filepath, object_container_name, object_name, parent_joint, child_joint):
        object_file = f"{os.environ['RIGGING_TOOL_ROOT']}{object_relative_filepath}"
        cmds.file(object_file, i=1)  # Import object file
        object_container = cmds.rename(object_container_name, f"{parent_joint}_{object_container_name}")  # Rename container

        for node in cmds.container(object_container, q=1, nl=1):
            cmds.rename(node, f"{parent_joint}_{node}", ignoreShape=1)  # Rename nodes

        object = f"{parent_joint}_{object_name}"

        constrained_grp = cmds.group(em=1, n=f"{object}_parentConstraint_grp")  # Create group for object
        cmds.parent(object, constrained_grp, a=1)  # Parent object to group

        parent_constraint = cmds.parentConstraint(parent_joint, constrained_grp, mo=0)[0]  # Create parent constraint

        cmds.connectAttr(f"{child_joint}.translateX", f"{constrained_grp}.scaleX")  # Connect translateX to scaleX

        scale_constraint = cmds.scaleConstraint(self.module_transform, constrained_grp, sk="x", mo=0)[0]  # Create scale constraint

        utils.add_node_to_container(object_container, [constrained_grp, parent_constraint, scale_constraint], ihb=1)  # Add nodes to container
        utils.add_node_to_container(self.container_name, object_container)  # Add container to module container

        return (object_container, object, constrained_grp)

    def initialize_module_transform(self, root_pos):
        control_grp_file = f"{os.environ['RIGGING_TOOL_ROOT']}/ControlObjects/Blueprint/controlGroup_control.ma"
        cmds.file(control_grp_file, i=1)  # Import control group file

        self.module_transform = cmds.rename("controlGroup_control", f"{self.module_namespace}:module_transform")  # Rename control group
        cmds.xform(self.module_transform, ws=1, a=1, t=root_pos)  # Set transform position
        
        
        if self.mirrored:
            duplicate_transform = cmds.duplicate(f"{self.original_module}:module_transform", po=1, n="TEMP_TRANSFORM")[0]
            empty_group = cmds.group(em=1)
            cmds.parent(duplicate_transform, empty_group, a=1)
            
            scale_attr = ".scaleX"
            if self.mirror_plane == "XZ":
                scale_attr = ".scaleY"
            elif self.mirror_plane =="XY":
                scale_attr = ".scaleZ"
                
            cmds.setAttr(f"{empty_group}{scale_attr}", -1)
            
            parent_constraint = cmds.parentConstraint(duplicate_transform, self.module_transform, mo=False)
            cmds.delete(parent_constraint)
            cmds.delete(empty_group)
            
            temp_locator = cmds.spaceLocator()[0]
            scale_constraint = cmds.scaleConstraint(f"{self.original_module}:module_transform", temp_locator, mo=0)[0]
            scale = cmds.getAttr(f"{temp_locator}.scaleX")
            cmds.delete([temp_locator, scale_constraint])
            
            print(f"my scale {scale}")
            cmds.xform(self.module_transform, os=1, scale=[scale, scale, scale])
        

        utils.add_node_to_container(self.container_name, self.module_transform, ihb=1)  # Add transform to container

        cmds.connectAttr(f"{self.module_transform}.scaleY", f"{self.module_transform}.scaleX")  # Connect scale attributes
        cmds.connectAttr(f"{self.module_transform}.scaleY", f"{self.module_transform}.scaleZ")
        
        

        cmds.aliasAttr("globalScale", f"{self.module_transform}.scaleY")  # Alias globalScale attribute

        cmds.container(self.container_name, e=1, pb=[f"{self.module_transform}.translate", "moduleTransform_T"])  # Publish translate attribute
        cmds.container(self.container_name, e=1, pb=[f"{self.module_transform}.rotate", "moduleTransform_R"])  # Publish rotate attribute
        cmds.container(self.container_name, e=1, pb=[f"{self.module_transform}.globalScale", "moduleTransform_globalScale"])  # Publish globalScale attribute

    def delete_hierarchy_representation(self, parent_joint):
        hierarchy_container = f"{parent_joint}_hierarchy_representation_container"  # Get hierarchy container name
        cmds.delete(hierarchy_container)  # Delete hierarchy container

    def create_orientation_control(self, parent_joint, child_joint):
        self.delete_hierarchy_representation(parent_joint)  # Delete existing hierarchy representation

        nodes = self.create_stretchy_object("/ControlObjects/Blueprint/orientation_control.ma", "orientation_control_container", "orientation_control", parent_joint, child_joint)  # Create stretchy object
        orientation_container = nodes[0]
        orientation_control = nodes[1]
        constrained_grp = nodes[2]

        cmds.parent(constrained_grp, self.orientation_controls_grp, r=1)  # Parent group to orientation controls group
        parent_joint_without_namespace = utils.strip_all_namespaces(parent_joint)[1]
        attr_name = f"{parent_joint_without_namespace}_orientation"

        cmds.container(orientation_container, e=1, pb=[f"{orientation_control}.rotateX", attr_name])  # Publish rotateX attribute
        cmds.container(self.container_name, e=1, pb=[f"{orientation_container}.{attr_name}", attr_name])  # Publish attribute to module container

        return orientation_control

    def get_joints(self):
        joint_basename = f"{self.module_namespace}:"
        joints = []

        for joint_inf in self.joint_info:
            joints.append(f"{joint_basename}{joint_inf[0]}")  # Get full joint name

        return joints

    def get_orientation_control(self, joint_name):
        return f"{joint_name}_orientation_control"  # Get orientation control name

    def orientation_controlled_joint_get_orientation(self, joint, clean_parent):
        new_clean_parent = cmds.duplicate(joint, po=1)[0]  # Duplicate joint

        if clean_parent not in cmds.listRelatives(new_clean_parent, p=1):
            cmds.parent(new_clean_parent, clean_parent, a=1)  # Parent duplicate joint

        cmds.makeIdentity(new_clean_parent, a=1, r=1, s=0, t=0)  # Freeze transformations
        orientation_control = self.get_orientation_control(joint)

        cmds.setAttr(f"{new_clean_parent}.rotateX", cmds.getAttr(f"{orientation_control}.rotateX"))  # Set rotateX attribute

        cmds.makeIdentity(new_clean_parent, a=1, r=1, s=0, t=0)  # Freeze transformations

        orientX = cmds.getAttr(f"{new_clean_parent}.jointOrientX")
        orientY = cmds.getAttr(f"{new_clean_parent}.jointOrientY")
        orientZ = cmds.getAttr(f"{new_clean_parent}.jointOrientZ")

        orientation_values = (orientX, orientY, orientZ)

        return (orientation_values, new_clean_parent)

    def lock_phase_2(self, module_info):
        joint_positions = module_info[0]
        num_joints = len(joint_positions)
        joint_orientations = module_info[1]
        orient_with_axis = False
        pure_orientations = False

        if joint_orientations[0] is None:
            orient_with_axis = True
            joint_orientations = joint_orientations[1]
        else:
            pure_orientation = True
            joint_orientations = joint_orientations[0]

        num_orientations = len(joint_orientations)
        joint_rotation_orders = module_info[2]
        num_rotation_orders = len(joint_rotation_orders)
        joint_preferred_angles = module_info[3]
        num_preferred_angles = 0

        if joint_preferred_angles is not None:
            num_preferred_angles = len(joint_preferred_angles)

        hook_object = module_info[4]
        root_transform = module_info[5]

        cmds.lockNode(self.container_name, l=0, lu=0)  # Unlock container
        cmds.delete(self.container_name)  # Delete container
        cmds.namespace(set=":")  # Set namespace to root

        joint_radius = 1
        if num_joints == 1:
            joint_radius = 1.5

        new_joints = []
        for i in range(num_joints):
            new_joint = ""
            cmds.select(cl=1)

            if orient_with_axis:
                new_joint = cmds.joint(n=f"{self.module_namespace}:blueprint_{self.joint_info[i][0]}",
                                       p=joint_positions[i], roo="xyz", rad=joint_radius)  # Create joint

                if i != 0:
                    cmds.parent(new_joint, new_joints[i-1], a=1)  # Parent joint
                    offset_index = i - 1

                    if offset_index < num_orientations:
                        cmds.joint(new_joints[offset_index], e=1, oj=joint_orientations[offset_index][0], sao=joint_orientations[offset_index][1])  # Orient joint
                        cmds.makeIdentity(new_joint, r=1, a=1)

            else:
                if i != 0:
                    cmds.select(new_joints[i-1])
                    joint_orientation = [0.0, 0.0, 0.0]

                if i < num_orientations:
                    joint_orientation = [joint_orientations[i][0], joint_orientations[i][1], joint_orientations[i][2]]

                new_joint = cmds.joint(n=f"{self.module_namespace}:blueprint_{self.joint_info[i][0]}",
                                       p=joint_positions[i], o=joint_orientation, roo="xyz", rad=joint_radius)  # Create joint

            new_joints.append(new_joint)

            if i < num_rotation_orders:
                cmds.setAttr(f"{new_joint}.rotateOrder", int(joint_rotation_orders[i]))  # Set rotate order

            if i < num_preferred_angles:
                cmds.setAttr(f"{new_joint}.preferredAngleX", joint_preferred_angles[i][0])
                cmds.setAttr(f"{new_joint}.preferredAngleY", joint_preferred_angles[i][1])
                cmds.setAttr(f"{new_joint}.preferredAngleZ", joint_preferred_angles[i][2])
                cmds.setAttr(f"{new_joint}.segmentScaleCompensate", 0)

        blueprint_grp = cmds.group(em=1, n=f"{self.module_namespace}:blueprint_joint_grp")  # Create group for blueprint joints
        cmds.parent(new_joints[0], blueprint_grp, a=1)  # Parent first joint to group

        creation_pose_grp_nodes = cmds.duplicate(blueprint_grp, n=f"{self.module_namespace}:creation_pose_joint_grp", rc=1)  # Duplicate group for creation pose
        creation_pose_grp = creation_pose_grp_nodes[0]

        creation_pose_grp_nodes.pop(0)

        i = 0
        for node in creation_pose_grp_nodes:
            renamed_node = cmds.rename(node, f"{self.module_namespace}:creation_pose_{self.joint_info[i][0]}")  # Rename nodes
            cmds.setAttr(f"{renamed_node}.visibility", 0)  # Hide nodes
            i += 1

        cmds.select(blueprint_grp, r=1)
        cmds.addAttr(at="bool", dv=0, ln="controlModulesInstalled", k=0)  # Add attribute for control modules
        
        hook_grp = cmds.group(em=1,n=f"{self.module_namespace}:HOOK_IN" )
        for obj in [blueprint_grp, creation_pose_grp]:
            cmds.parent(obj, hook_grp, a=1)
        
        
        setting_locator = cmds.spaceLocator(n=f"{self.module_namespace}:SETTINGS")[0]  # Create settings locator
        cmds.setAttr(f"{setting_locator}.visibility", 0)  # Hide settings locator

        cmds.select(setting_locator, r=1)
        cmds.addAttr(at="enum", ln="activeModule", en="None:", k=0)  # Add active module attribute
        cmds.addAttr(at="float", ln="creationPoseWeight", dv=1, k=0)  # Add creation pose weight attribute

        i = 0
        utility_nodes = []
        for joint in new_joints:
            if i < (num_joints-1) or num_joints == 1:
                add_node = cmds.shadingNode("plusMinusAverage", n=f"{joint}_addRotations", au=1)  # Create plusMinusAverage node
                cmds.connectAttr(f"{add_node}.output3D", f"{joint}.rotate", f=1)  # Connect output to rotate
                utility_nodes.append(add_node)

                dummy_rotations_multiply = cmds.shadingNode("multiplyDivide", n=f"{joint}_dummyRotationsMultiply", au=1)  # Create multiplyDivide node
                cmds.connectAttr(f"{dummy_rotations_multiply}.output", f"{add_node}.input3D[0]", f=1)  # Connect output to input
                utility_nodes.append(dummy_rotations_multiply)

            if i > 0:
                original_tx = cmds.getAttr(f"{joint}.tx")
                add_tx_node = cmds.shadingNode("plusMinusAverage", n=f"{joint}_addTx", au=1)  # Create plusMinusAverage node
                cmds.connectAttr(f"{add_tx_node}.output1D", f"{joint}.translateX", f=1)  # Connect output to translateX
                utility_nodes.append(add_tx_node)

                original_tx_multiply = cmds.shadingNode("multiplyDivide", n=f"{joint}_original_Tx", au=1)  # Create multiplyDivide node
                cmds.setAttr(f"{original_tx_multiply}.input1X", original_tx, l=1)  # Set input1X attribute
                cmds.connectAttr(f"{setting_locator}.creationPoseWeight", f"{original_tx_multiply}.input2X", f=1)  # Connect creationPoseWeight to input2X

                cmds.connectAttr(f"{original_tx_multiply}.outputX", f"{add_tx_node}.input1D[0]", f=1)  # Connect output to input
                utility_nodes.append(original_tx_multiply)
            else:
                if root_transform:
                    original_translates = cmds.getAttr(f"{joint}.translate")[0]
                    add_translate_node = cmds.shadingNode("plusMinusAverage", n=f"{joint}_addTranslate", au=1)  # Create plusMinusAverage node
                    cmds.connectAttr(f"{add_translate_node}.output3D", f"{joint}.translate", f=1)  # Connect output to translate
                    utility_nodes.append(add_translate_node)

                    original_translate_multiply = cmds.shadingNode("multiplyDivide", n=f"{joint}_original_Translate", au=1)  # Create multiplyDivide node
                    cmds.setAttr(f"{original_translate_multiply}.input1", original_translates[0], original_translates[1], original_translates[2], typ="double3")  # Set input attributes

                    for attr in ["X", "Y", "Z"]:
                        cmds.connectAttr(f"{setting_locator}.creationPoseWeight", f"{original_translate_multiply}.input2{attr}")  # Connect creationPoseWeight to inputs

                    cmds.connectAttr(f"{original_translate_multiply}.output", f"{add_translate_node}.input3D[0]", f=1)  # Connect output to input
                    utility_nodes.append(original_translate_multiply)

                    original_scales = cmds.getAttr(f"{joint}.scale")[0]
                    add_scale_node = cmds.shadingNode("plusMinusAverage", n=f"{joint}_addScale", au=1)  # Create plusMinusAverage node
                    cmds.connectAttr(f"{add_scale_node}.output3D", f"{joint}.scale", f=1)  # Connect output to scale
                    utility_nodes.append(add_scale_node)

                    original_scale_multiply = cmds.shadingNode("multiplyDivide", n=f"{joint}_original_Scale", au=1)  # Create multiplyDivide node
                    cmds.setAttr(f"{original_scale_multiply}.input1", original_scales[0], original_scales[1], original_scales[2], typ="double3")  # Set input attributes

                    for attr in ["X", "Y", "Z"]:
                        cmds.connectAttr(f"{setting_locator}.creationPoseWeight", f"{original_scale_multiply}.input2{attr}")  # Connect creationPoseWeight to inputs

                    cmds.connectAttr(f"{original_scale_multiply}.output", f"{add_scale_node}.input3D[0]", f=1)  # Connect output to input
                    utility_nodes.append(original_scale_multiply)

            i += 1

        blueprint_nodes = utility_nodes
        blueprint_nodes.append(blueprint_grp)
        blueprint_nodes.append(creation_pose_grp)

        blueprint_container = cmds.container(n=f"{self.module_namespace}:blueprint_container")  # Create blueprint container
        utils.add_node_to_container(blueprint_container, blueprint_nodes, ihb=1)  # Add nodes to container

        module_grp = cmds.group(em=1, n=f"{self.module_namespace}:module_grp")  # Create module group
        
        for obj in [hook_grp, setting_locator]:
            cmds.parent(obj, module_grp, a=1)  # Parent obj to module_grp

        module_container = cmds.container(n=f"{self.module_namespace}:module_container")  # Create module container
        utils.add_node_to_container(module_container, [module_grp, hook_grp, setting_locator, blueprint_container], include_shapes=1)  # Add nodes to container

        cmds.container(module_container, e=1, pb=[f"{setting_locator}.activeModule", "activeModule"])  # Publish activeModule attribute
        cmds.container(module_container, e=1, pb=[f"{setting_locator}.creationPoseWeight", "creationPoseWeight"])  # Publish creationPoseWeight attribute

        cmds.select(module_grp)
        cmds.addAttr(at="float", ln="hierarchicalScale")
        cmds.connectAttr(f"{hook_grp}.scaleY", f"{module_grp}.hierarchicalScale")


    def UI(self, blueprint_UI_instance, parent_column_layout):
        self.blueprint_UI_instance = blueprint_UI_instance
        self.parent_column_layout = parent_column_layout
        self.UI_custom()  # Call custom UI method

    def create_rotation_order_UI_control(self, joint):
        joint_name = utils.strip_all_namespaces(joint)[1]
        attr_control_group = cmds.attrControlGrp(attribute=f"{joint}.rotateOrder", label=joint_name)  # Create attribute control group
        
    def delete(self):
        cmds.lockNode(self.container_name, l=0, lu=0)
        
        valid_module_info = utils.find_all_module_names("/Modules/Blueprint")
        valid_module = valid_module_info[0]
        valid_module_names = valid_module_info[1]
        
        hooked_modules = set()
        for joint_inf in self.joint_info:
            joint = joint_inf[0]
            translation_control = self.get_translation_control(f"{self.module_namespace}:{joint}")
            
            connections = cmds.listConnections(translation_control)
            for connection in connections:
                modules_instance = utils.strip_leading_namespace(connection)
                
                if modules_instance != None:
                    split_string = modules_instance[0].partition("__")
                    
                    if modules_instance[0] != self.module_namespace and split_string[0] in valid_module_names:
                        index = valid_module_names.index(split_string[0])
                        hooked_modules.add((valid_module[index], split_string[2]))
                        
        for module in hooked_modules:
            mod = __import__(f"Blueprint.{module[0]}", {}, {}, [module[0]])
            ModuleClass = getattr(mod, mod.CLASS_NAME)
            modules_inst = ModuleClass(module[1], None)
            modules_inst.rehook(None)
            
        
        
        module_transform = f"{self.module_namespace}:module_transform"
        module_transform_parent = cmds.listRelatives(module_transform, p=1)
        
        
        cmds.delete(self.container_name)
        
        
        cmds.namespace(set=":")
        cmds.namespace(rm=self.module_namespace)
        
        if module_transform_parent != None:
            parent_group = module_transform_parent[0]
            children = cmds.listRelatives(parent_group, c=1)
            children = cmds.ls(children, tr=1)
            
            if len(children) == 0:
                cmds.select(parent_group, r=1)
                import System.GroupSelected as group_selected
                importlib.reload(group_selected)
                group_selected.UngroupSelected()
            
        
    def rename_module_instance(self, new_name):
        if new_name == self.user_specified_name:
            return True


        if utils.does_user_specified_name_exist(new_name):
            try:
                if cmds.window(confirm_dialog, exists=True):
                    cmds.deleteUI(confirm_dialog, window=True)
            except:
                pass
                
                try: 
                    confirm_dialog = cmds.confirmDialog(t="Name Conflict", m=f'Name {new_name}\nalready exists, aborting rename')
                    return False
                except RuntimeError as e:
                    # Suppress the RuntimeError if it is due to an existing confirmDialog
                    if 'Only one confirmDialog may exist at a time' in str(e):
                        pass
                    else:
                        raise
                    
            
        
        else:
            new_namespace = f"{self.module_name}__{new_name}"
            cmds.lockNode(self.container_name, l=0, lu=0)
            cmds.namespace(set=":")
            cmds.namespace(add=new_namespace)
            cmds.namespace(set=":")
            
            cmds.namespace(mv=[self.module_namespace, new_namespace])
            cmds.namespace(rm=self.module_namespace)
            self.module_namespace = new_namespace
            self.container_name = f"{self.module_namespace}:module_container"
            
            cmds.lockNode(self.container_name, l=1, lu=1)
            return True
            
            
    def initialize_hook(self, root_translation_control):
        unhooked_locator = cmds.spaceLocator(n=f"{self.module_namespace}:unhookedTarget")[0]
        cmds.pointConstraint(root_translation_control, unhooked_locator, o=[0, 0.001, 0])
        cmds.setAttr(f"{unhooked_locator}.visibility", 0)
        
        if self.hook_object == None:
            self.hook_object = unhooked_locator
            
        root_pos = cmds.xform(root_translation_control, q=1, ws=1, t=1)
        target_pos = cmds.xform(self.hook_object, q=1, ws=1, t=1)
        
        cmds.select(cl=1)
        
        root_joint_without_namespace = "hook_root_joint"
        root_joint = cmds.joint(n=f"{self.module_namespace}:{root_joint_without_namespace}", p=root_pos)
        cmds.setAttr(f"{root_joint}.visibility", 0)
            
        target_joint_without_namespace = "hook_target_joint"
        target_joint = cmds.joint(n=f"{self.module_namespace}:{target_joint_without_namespace}", p=target_pos)
        cmds.setAttr(f"{target_joint}.visibility", 0)
        
        cmds.joint(root_joint, e=1, oj="xyz", sao="yup")
        hook_grp = cmds.group([root_joint, unhooked_locator], n=f"{self.module_namespace}:hook_grp", p=self.module_grp)
        hook_container = cmds.container(n=f"{self.module_namespace}:hook_container")
        utils.add_node_to_container(hook_container, hook_grp, ihb=1)
        utils.add_node_to_container(self.container_name, hook_container)
        
        for joint in [root_joint, target_joint]:
            joint_name = utils.strip_all_namespaces(joint)[1]
            cmds.container(hook_container, e=1, pb=[f"{joint}.rotate", f"{joint_name}_R"])
            
        ik_nodes = utils.basic_stretchy_IK(root_joint, target_joint, hook_container, lockMinimumLength=0)
        ik_handle = ik_nodes["ik_handle"]
        root_locator = ik_nodes["root_locator"]
        end_locator = ik_nodes["end_locator"]
        poleVectorObject = ik_nodes["poleVectorObject"]
        
        root_point_constraint = cmds.pointConstraint(root_translation_control, root_joint, mo=0, n=f"{root_joint}_pointConstraint")[0]
        target_point_constraint = cmds.pointConstraint(self.hook_object, end_locator, mo=0, n=f"{self.module_namespace}:hook_pointConstraint")[0]
        
        utils.add_node_to_container(hook_container, [root_point_constraint, target_point_constraint])
        
        for node in [ik_handle, root_locator, end_locator, poleVectorObject]:
            cmds.parent(node, hook_grp, a=1)
            cmds.setAttr(f"{node}.visibility", 0)
            
        object_nodes = self.create_stretchy_object("/ControlObjects/Blueprint/hook_representation.ma", "hook_representation_container", "hook_representation", root_joint, target_joint)
        
        constrained_grp = object_nodes[2]
        cmds.parent(constrained_grp, hook_grp, a=1)
        
        hook_representation_container = object_nodes[0]
        cmds.container(self.container_name, e=1, rn=hook_representation_container)
        utils.add_node_to_container(hook_container, hook_representation_container)
        
        
    def rehook(self, new_hook_object):
        old_hook_object = self.find_hook_object()
        
        self.hook_object = f"{self.module_namespace}:unhookedTarget"
        
        if new_hook_object != None:
            if new_hook_object.find("_translation_control") != -1:
                split_string = new_hook_object.split("_translation_control")
                if split_string[1] == "":
                    if utils.strip_leading_namespace(new_hook_object)[0] != self.module_namespace:
                        self.hook_object = new_hook_object
                        
        if self.hook_object == old_hook_object:
            return
        
        self.unconstrain_root_to_hook()
        
        cmds.lockNode(self.container_name, l=0, lu=0)
        hook_constraint = f"{self.module_namespace}:hook_pointConstraint"
        cmds.connectAttr(f"{self.hook_object}.parentMatrix[0]", f"{hook_constraint}.target[0].targetParentMatrix", f=1)
        cmds.connectAttr(f"{self.hook_object}.translate", f"{hook_constraint}.target[0].targetTranslate", f=1)
        cmds.connectAttr(f"{self.hook_object}.rotatePivot", f"{hook_constraint}.target[0].targetRotatePivot", f=1)
        cmds.connectAttr(f"{self.hook_object}.rotatePivotTranslate", f"{hook_constraint}.target[0].targetRotateTranslate", f=1)
        
        cmds.lockNode(self.container_name, l=1, lu=1)
        
        
    def find_hook_object(self):
        hook_constraint = f"{self.module_namespace}:hook_pointConstraint"
        source_attr = cmds.connectionInfo(f"{hook_constraint}.target[0].targetParentMatrix", sfd=1)
        source_node = str(source_attr).rpartition(".")[0]
        return source_node
    
    def find_hook_object_for_lock(self):
        hook_object = self.find_hook_object()
        
        if hook_object == f"{self.module_namespace}:unhookedTarget":
            hook_object = None
        else:
            self.rehook(None)
        
        return hook_object
    
    def lock_phase_3(self, hook_object):
        module_container = f"{self.module_namespace}:module_container"
        if hook_object != None:
            hook_object_module_node = utils.strip_leading_namespace(hook_object)
            hook_obj_module = hook_object_module_node[0]
            hook_obj_joint = hook_object_module_node[1].split("_translation_control")[0]
            
            hook_obj = f"{hook_obj_module}:blueprint_{hook_obj_joint}"
            
            parent_constraint = cmds.parentConstraint(hook_obj, f"{self.module_namespace}:HOOK_IN", mo=1, n=f"{self.module_namespace}:hook_parent_constraint")[0]
            scale_constraint = cmds.scaleConstraint(hook_obj,  f"{self.module_namespace}:HOOK_IN", mo=1, n=f"{self.module_namespace}:hook_scale_constraint")[0]
            
            
            utils.add_node_to_container(module_container, [parent_constraint, scale_constraint])
        cmds.lockNode(module_container, l=1, lu=1)
        
        
    def snap_root_to_hook(self):
        root_control = self.get_translation_control(f"{self.module_namespace}:{self.joint_info[0][0]}")
        hook_object = self.find_hook_object()
        
        if hook_object == f"{self.module_namespace}:unhookedTarger":
            return
        
        hook_object_pos = cmds.xform(hook_object, q=1, ws=1, t=1)
        cmds.xform(root_control, ws=1, a=1, t=hook_object_pos)
        
    def constrain_root_to_hook(self):
        root_control = self.get_translation_control(f"{self.module_namespace}:{self.joint_info[0][0]}")
        hook_object = self.find_hook_object()
        
        if hook_object == f"{self.module_namespace}:unhookedTarger":
            return
        
        cmds.lockNode(self.container_name, l=0, lu=0)
        
        cmds.pointConstraint(hook_object, root_control, mo=0, n=f"{root_control}_hookConstraint")
        cmds.setAttr(f"{root_control}.translate", l=1)
        cmds.setAttr(f"{root_control}.visibility", l=0)
        cmds.setAttr(f"{root_control}.visibility", 0)
        cmds.setAttr(f"{root_control}.visibility", l=1)
        
        cmds.select(cl=1)
        
        cmds.lockNode(self.container_name, l=1, lu=1)
        
        
        
    def unconstrain_root_to_hook(self):
        cmds.lockNode(self.container_name, l=0, lu=0)
        
        root_control = self.get_translation_control(f"{self.module_namespace}:{self.joint_info[0][0]}")
        root_control_hook_constraint = f"{root_control}_hookConstraint"
        
        if cmds.objExists(root_control_hook_constraint):
            cmds.delete(root_control_hook_constraint)
            
            cmds.setAttr(f"{root_control}.translate", l=0)
            cmds.setAttr(f"{root_control}.visibility", l=0)
            cmds.setAttr(f"{root_control}.visibility", 1)
            cmds.setAttr(f"{root_control}.visibility", l=1)
            
            cmds.select(root_control, r=1)
            cmds.setToolTo("moveSuperContext")
            
        cmds.lockNode(self.container_name, l=1, lu=1)
        
    def is_root_constrained(self):
        root_control = self.get_translation_control(f"{self.module_namespace}:{self.joint_info[0][0]}")
        root_control_hook_constraint = f"{root_control}_hookConstraint"
        return cmds.objExists(root_control_hook_constraint)
    
    def can_module_be_mirrored(self):
        return self.module_can_be_mirrored
    
    def mirror(self, original_module, mirror_plane, rotation_function, translation_function):
        self.mirrored = True
        self.original_module = original_module
        self.mirror_plane = mirror_plane
        self.rotation_function = rotation_function
        
        self.install()
        
        cmds.lockNode(self.container_name,l=0, lu=0)
        
        for joint_info in self.joint_info:
            joint_name = joint_info[0]
            
            
            original_joint = f"{self.original_module}:{joint_name}"
            new_joint = f"{self.module_namespace}:{joint_name}"
            
            original_rotation_order = cmds.getAttr(f"{original_joint}.rotateOrder")
            cmds.setAttr(f"{new_joint}.rotateOrder", original_rotation_order)
            
        index = 0
        for joint_info in self.joint_info:
            mirror_pole_vector_locator = False
            if index < len(self.joint_info) - 1:
                mirror_pole_vector_locator = True
                
            joint_name = joint_info[0]
            original_joint = f"{self.original_module}:{joint_name}"
            new_joint = f"{self.module_namespace}:{joint_name}"
            
            original_translation_control = self.get_translation_control(original_joint)
            new_translation_control = self.get_translation_control(new_joint)
        
            original_translation_control_position = cmds.xform(original_translation_control, q=1, ws=1, t=1)
            
            if self.mirror_plane == "YZ":
                original_translation_control_position[0] *= -1  
            elif self.mirror_plane == "XZ":
                original_translation_control_position[1] *= -1
            elif self.mirror_plane == "XY":
                original_translation_control_position[2] *= -1
                
                
            cmds.xform(new_translation_control, ws=1, a=1, t=original_translation_control_position)
            
            if mirror_pole_vector_locator:
                original_pole_vector_locator = f"{original_translation_control}_poleVectorLocator"
                new_pole_vector_locator = f"{new_translation_control}_poleVectorLocator"
                original_pole_vector_locator_position = cmds.xform(original_pole_vector_locator, q=1, ws=1, t=1)
                
                if self.mirror_plane == "YZ":
                    original_pole_vector_locator_position[0] *= -1  
                elif self.mirror_plane == "XZ":
                    original_pole_vector_locator_position[1] *= -1
                elif self.mirror_plane == "XY":
                    original_pole_vector_locator_position[2] *= -1
                    
                cmds.xform(new_pole_vector_locator, ws=1, a=1, t=original_pole_vector_locator_position)
                
            index += 1
                
            
        self.mirror_custom(original_module)
        
        module_group = f"{self.module_namespace}:module_grp"
        cmds.select(module_group, r=1)
        
        enum_names = "none:x:y:z"
        cmds.addAttr(at="enum", en=enum_names, ln="mirrorInfo", k=0)

        enum_value = 0
        if translation_function == "mirrored":
            if mirror_plane == "YZ":
                enum_value = 1
            elif mirror_plane == "XZ":
                enum_value = 1
            elif mirror_plane == "XY":
                enum_value = 1
                
        cmds.setAttr(f"{module_group}.mirrorInfo", enum_value)
        
        linked_attribute = "mirrorLinks"
        cmds.lockNode(f"{original_module}:module_container", l=0, lu=0)
        
        for module_link in ((original_module, self.module_namespace),(self.module_namespace, original_module)):
            module_group = f"{module_link[0]}:module_grp"
            attribute_value = f"{module_link[1]}__"
            
            if mirror_plane == "YZ":
                attribute_value += "X"
            elif mirror_plane == "XZ":
                attribute_value += "Y"
            elif mirror_plane == "XY":
                attribute_value += "Z"
                
            cmds.select(module_group)
            cmds.addAttr(dt="string", ln=linked_attribute, k=0)
            cmds.setAttr(f"{module_group}.{linked_attribute}", attribute_value, typ="string")
            
        for c in [f"{original_module}:module_container", self.container_name]:
            cmds.lockNode(c, l=1, lu=1)
            
        cmds.select(cl=1)
            
            
            